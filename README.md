# SpewTube Bot
A maubot plugin that scans your chats for links to Spotify tracks, and finds corresponding links on YouTube. Additionally, it provides commands that let you search for music/videos on Spotify and YouTube.

<img width="40%" height="40%" alt="spotify" src="https://github.com/user-attachments/assets/81f1a6dd-5383-478a-be9c-42a0a623707a" />
<img width="40%" height="40%" alt="youtube" src="https://github.com/user-attachments/assets/928ee3bd-e1fa-46bf-adcf-9c9e7700ec06" />


## Installation
The plugin requires the following Python packages that are not part of the default maubot installation:
* yt-dlp
* yt-dlp-ejs
* spotipyFree

For some reason `spotipyFree` doesn't pull all required dependencies, so install `redis` and `websockets` too.

These packages are not installed automatically with the plugin. They can be installed the same way you [install maubot](https://docs.mau.fi/maubot/usage/setup/index.html#production-setup):

```
cd maubot
source ./bin/activate
pip install --upgrade yt-dlp yt-dlp-ejs spotipyFree redis websockets
```

Other than that, `yt-dlp` needs `deno` or some other JavaScript runtime to solve YouTube challenges, so install that too as described [here](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

`spotipyFree` and `yt-dlp` can break often, so keep them somewhat up to date.

## Usage
Plugin is scanning for incoming Spotify links when `enable_redirect` if set to `true`. You just send a link to Spotify track in the chat and bot should pick that up. As of now it only supports links to tracks, not artists nor albums.

Additionally, plugin supports searching in YouTube and Spotify using following commands:
* `!yt <query>` - alternatively `!youtube`; search for music/videos in YouTube
* `!sp <query>` - alternatively `!spotify`; search for music tracks in Spotify
* `!music <query>` - search using both YouTube and Spotify

## Configuration  
You can configure the plugin in maubot's control panel.  
* `enable_redirect` - controls whether the plugin will try to respond to Spotify links with corresponding YouTube links (default: `true`) 
* `max_width` - maximum width of YouTube video thumbnail  
* `max_height` - maximum height of YouTube video thumbnail  

## Disclaimer  
This plugin is not affiliated with Spotify nor YouTube. It is not intended for commercial use or any purpose that violates Terms of Service of mentioned services. By using this plugin, you acknowledge that you will not use it in a way that infringes on these service's terms.
