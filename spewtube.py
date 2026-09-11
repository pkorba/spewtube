from typing import Any, Tuple, Type

import filetype
import yt_dlp
from SpotipyFree import Spotify
from aiohttp import ClientTimeout, ClientError
from mautrix.errors import MatrixResponseError
from mautrix.types import TextMessageEventContent, MessageType, Format
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from spotapi.exceptions import SongError
from maubot import Plugin, MessageEvent
from maubot.handlers import command


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("enable_redirect")
        helper.copy("max_width")
        helper.copy("max_height")


class SpewTubeBot(Plugin):
    sp = Spotify()

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    @command.passive(
        r"https?://(?:open|play)\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]+)",
        multiple=True
    )
    async def spewtube(self, evt: MessageEvent, matches: list[tuple[str, str]]) -> None:
        if not self.config["enable_redirect"]:
            return
        if evt.sender == self.client.mxid:
            return
        await evt.mark_read()
        for url in matches:
            yt_search_query = await self.loop.run_in_executor(None, self._spot_search, url[1])
            info = await self.loop.run_in_executor(None, self._yt_search, yt_search_query)
            if not info:
                continue
            info = await self._parse_info(info)
            content = await self._prepare_message(info)
            await evt.reply(content)

    def _spot_search(self, track_id: str) -> str:
        try:
            song = self.sp.track(track_id)
        except SongError as e:
            self.log.error(f"Identifying track failed: {e}")
            return ""
        title = song.get("name", "")
        artist = ""
        artists = song.get("artists", "")
        if artists:
            artist = artists[0].get("name")
        return f"{title}{f' - {artist}' if artist else ''}"

    @command.new(name="yt", aliases=["youtube"], help="Search on YouTube")
    @command.argument("query", pass_raw=True, required=True)
    async def youtube(self, evt: MessageEvent, query: str) -> None:
        await evt.mark_read()
        if not query:
            await evt.reply("> **Usage:** !yt <query>")
            return
        info = await self.loop.run_in_executor(None, self._yt_search, query)
        if not info:
            await evt.reply(f"> No results found for **{query}**")
            return
        info = await self._parse_info(info)
        content = await self._prepare_message(info)
        await evt.reply(content)

    def _yt_search(self, query: str) -> dict[str, str] | None:
        if not query:
            return None
        ydl_opts = {
            'default_search': 'ytsearch',
            'max_downloads': 1,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            if 'entries' in info and len(info['entries']) > 0:
                result = info['entries'][0]
                extracted_info = {
                    'webpage_url': result.get('webpage_url'),
                    'thumbnails': result.get('thumbnails'),
                    'title': result.get('title'),
                    'uploader': result.get('uploader'),
                    'duration_string': result.get('duration_string'),
                    'view_count': result.get('view_count'),
                }
                return extracted_info
        return None

    async def _parse_info(self, info: dict[str, Any]) -> dict[str, Any]:
        info["view_count"] = await self._parse_votes(int(info['view_count']))
        info['thumb'], info['width'], info['height'] = await self._parse_photos(info["thumbnails"])
        return info

    async def _prepare_message(self, info: dict[str, Any]) -> TextMessageEventContent:
        html = await self._get_url_title(info['title'], info['webpage_url'])
        body = await self._get_url_title(info['title'], info['webpage_url'], False)
        html += await self._get_elem("Author", info['uploader'])
        body += await self._get_elem("Author", info['uploader'], False)
        html += await self._get_elem("Length", info['duration_string'])
        body += await self._get_elem("Length", info['duration_string'], False)
        html += await self._get_elem("Views", info['view_count'])
        body += await self._get_elem("Views", info['view_count'], False)
        html += await self._get_image(
            info['thumb'],
            f"Thumbnail for {info['title']}",
            (info["width"], info["height"])
        )
        body += await self._get_image(
            info['thumb'],
            f"Thumbnail for {info['title']}",
            (info["width"], info["height"]),
            False
        )
        html += await self._get_footer("YouTube")
        body += await self._get_footer("YouTube", False)

        html = f"<blockquote>{html}</blockquote>"

        content = TextMessageEventContent(
            msgtype=MessageType.NOTICE,
            format=Format.HTML,
            body=body,
            formatted_body=html
        )
        return content

    async def _parse_votes(self, value: int) -> str:
        """
        Get shortened representation of a number of interactions
        :param value: number of interactions
        :return: shortened number
        """
        if not value:
            return ""
        millions = divmod(value, 1000000)
        thousands = divmod(millions[1], 1000)
        if millions[0]:
            formatted_value = f"{millions[0]}.{millions[1] // 10000}M"
        elif thousands[0]:
            formatted_value = f"{thousands[0]}.{thousands[1] // 100}K"
        else:
            formatted_value = f"{thousands[1]}"
        return formatted_value

    async def _parse_photos(self, thumbnails: list[Any]) -> Tuple[str, int, int]:
        thumbs = [thumb for thumb in thumbnails if thumb.get("width")]
        for thumb in thumbs:
            if (
                thumb["height"] > self.config["max_height"]
                or thumb["width"] > self.config["max_width"]
            ):
                new_thumb = await self._get_thumbnail_url(thumb["url"].split("?")[0])
                width, height = await self._scale_dimensions(
                    int(thumb['width']),
                    int(thumb['height'])
                )
                return new_thumb, width, height

        new_thumb = await self._get_thumbnail_url(thumbs[-1]["url"].split("?")[0])
        width, height = await self._scale_dimensions(
            int(thumbs[-1]['width']),
            int(thumbs[-1]['height'])
        )
        return new_thumb, width, height

    async def _get_url_title(self, title: str, url: str, is_html: bool = True) -> str:
        if not url or not title:
            return ""
        if is_html:
            return f"<b>{await self._get_link(url, title, is_html)}</b><br>"
        return f"> {await self._get_link(url, f"**{title}**", is_html)}  \n>  \n"

    async def _get_link(self, url: str, text: str, is_html: bool = True) -> str:
        """
        Return a link as HTML or Markdown
        :param url: address
        :param text: displayed text
        :param is_html: True for HTML, False for Markdown
        :return: formatted string with a link
        """
        # HTML
        if is_html:
            return f"<a href=\"{url}\">{text}</a>"
        # Markdown
        return f"[{text}]({url})"

    async def _get_elem(self, elem_name: str, elem: str, is_html: bool = True) -> str:
        if not elem:
            return ""
        if is_html:
            return f"<blockquote><b>{elem_name}:</b> {elem}</blockquote>"
        return f"> > **{elem_name}:** {elem}  \n>  \n"

    async def _get_footer(self, engine: str, is_html: bool = True) -> str:
        if not engine:
            return ""
        if is_html:
            return f"<br><b><sub>Results from {engine}</sub></b>"
        return f"> **Results from {engine}**"

    async def _get_image(
        self,
        src: str,
        alt: str = "",
        size: Tuple[int, int] = (0, 0),
        is_html: bool = True
    ) -> str:
        """
        Get inline image
        :param src: source url
        :param alt: alternative text
        :param size: width, height
        :param is_html: True for HTML, False for Markdown
        :return: formatted string with inline image
        """
        if not src:
            return ""
        width = f"width=\"{size[0]}\" " if size[0] else ""
        height = f"height=\"{size[1]}\" " if size[1] else ""
        # HTML
        if is_html:
            return f"<img src=\"{src}\" alt=\"{alt}\" {width}{height}/>"
        # Markdown
        return f"![{alt}]({src})"

    async def _get_thumbnail_url(self, url: str) -> str:
        """
        Download thumbnail from external source and upload it to Matrix server
        :param url: external URL to the thumbnail
        :return: Matrix mxc image URL
        """
        # Download image from external source
        data = await self._download_image(url)
        content_type = await self._get_content_type(data)
        if not content_type:
            return ""
        return await self._upload_media(data, content_type.mime, f"image.{content_type.extension}")

    async def _download_image(self, url: str) -> bytes | None:
        """
        Download image from external URL
        :param url: URL to an image
        :return: image data as bytes or None if download fails for any reason
        """
        timeout = ClientTimeout(total=20)
        headers = {"User-Agent": "WhatsApp/2"}
        try:
            response = await self.http.get(
                url,
                headers=headers,
                timeout=timeout,
                raise_for_status=True
            )
            return await response.read()
        except ClientError as e:
            self.log.error(f"Downloading image - connection failed: {e}")

    async def _get_content_type(self, data: bytes) -> Any:
        """
        Get content type of provided image
        :param data: image file as bytes
        :return: image content type
        """
        if not data:
            return None
        try:
            content_type = await self.loop.run_in_executor(None, filetype.guess, data)
            if not content_type:
                self.log.error("Failed to determine file type")
                return None
            if content_type not in filetype.image_matchers:
                self.log.error("Downloaded file is not an image")
                return None
        except TypeError as e:
            self.log.error(f"Failed to determine file type: {e}")
            return None
        return content_type

    async def _upload_media(self, data: bytes, mime: str, name: str) -> str:
        """
        Upload image to Matrix server
        :param data: image data
        :param mime: image mimetype
        :param name: image name
        :return: MXC URL address to the image
        """
        try:
            # Upload image to Matrix server
            return await self.client.upload_media(
                data=data,
                mime_type=mime,
                filename=name,
                size=len(data))
        except (ValueError, MatrixResponseError) as e:
            self.log.error(f"Uploading image to Matrix server: {e}")
            return ""

    async def _scale_dimensions(self, width: int, height: int) -> Tuple[int, int]:
        max_width = self.config["max_width"]
        max_height = self.config["max_height"]
        if not max_width or not max_height or not width or not height:
            return 0, 0

        # Calculate scale factors
        scale_width = max_width / width
        scale_height = max_height / height

        # Choose the minimal scale to fit within constraints without enlarging
        scale = min(1, scale_width, scale_height)

        # Calculate new dimensions
        new_width = int(width * scale)
        new_height = int(height * scale)

        return new_width, new_height

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
