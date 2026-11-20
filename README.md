# iPhone Use for Windows

A Codex skill for using a real iPhone from Windows through iPhoneMirror and local MCP.
Ask Codex to look at the screen, tap a visible control, swipe, return to Home Screen,
or open the App Switcher. The MCP path uses iPhone screenshots and device input directly.

## Install with Codex

Open Codex on a Windows 10 or 11 x64 PC and paste this request:

> Install the iPhone Use for Windows skill from
> https://github.com/Ray-zuo/iphone-use-windows/tree/main/skills/iphone-use-windows .
> Run the skill's installer, register its local MCP server, and verify a screenshot
> from my connected iPhone. Tell me when I need to touch the phone.

中文也可以直接复制这句：

> 安装 https://github.com/Ray-zuo/iphone-use-windows/tree/main/skills/iphone-use-windows 这个 skill。运行自带安装器，接入本地 MCP，并用我的 iPhone 验证真机截图。需要我在手机上确认时告诉我。

The installer downloads iPhoneMirror and iPhone-mcp, checks the downloads, and
registers the `iphone-mcp` server in Codex. It reuses healthy USB drivers and guides
you through any missing setup. First use may require a USB data cable, unlocking
the phone, tapping **Trust This Computer**, enabling iOS Developer Mode for direct
control, or confirming a Windows driver prompt.

After setup, open a fresh Codex chat to load the server. Try **“Show me what’s on
my iPhone”** or **“Go to my iPhone’s Home Screen and open Camera.”**

## Install from a local checkout

```powershell
& .\skills\iphone-use-windows\scripts\install.ps1
```

Use `-SkipDrivers` if the USB capture drivers are already working. Use
`-ConfigureOnly` to download and register the MCP without diagnosing the phone.
See the [setup guide](skills/iphone-use-windows/references/setup.md#local-mcp)
for connection details, and the [CLI reference](skills/iphone-use-windows/references/cli.md)
for the standalone HTTP CLI.

## Controls

| iPhoneMirror mouse input | iPhone action | MCP tool |
|---|---|---|
| Left click | Tap | `tap` |
| Right click | Return to Home Screen | `press_shortcut` with `home` |
| Middle click | Open App Switcher | `press_shortcut` with `app_switcher` |

The bundled installer targets USB capture and direct touch control. Wireless
use requires an iPhoneMirror runtime with AirPlay and a supported control
transport. The device status reports supported actions. The skill verifies
the screen after an input.

## License

The skill, its bootstrap script, and the standalone CLI are [MIT licensed](LICENSE).
The installer downloads [iPhoneMirror](https://github.com/RayrenSX/iPhoneMirror)
and [iPhone-mcp](https://github.com/RayrenSX/iPhone-mcp) separately under their
upstream licenses. No upstream binaries are bundled here.
