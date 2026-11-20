"""Message catalog for iphone.py.

Languages: en (English), vi (Tiếng Việt), zh (简体中文), ja (日本語), ko (한국어).
Selection order: --lang flag > IPHONE_USE_LANG env > "lang" in config.json > Windows UI language > en.

To add a language: add its code to LANGUAGES, add a column to every entry in MESSAGES (missing
entries fall back to English), and optionally map its Windows LANGID / locale prefix in detect().

Machine-readable tokens (`screenshot:`, `zoom:`, `READY`, `NOT READY`, error codes like
CONTROL_NOT_AVAILABLE) are intentionally never translated so agents and scripts can parse them.
"""
from __future__ import annotations

import locale
import os
import sys

LANGUAGES = {
    "en": "English",
    "vi": "Tiếng Việt",
    "zh": "简体中文",
    "ja": "日本語",
    "ko": "한국어",
}

_current = "en"

MESSAGES: dict[str, dict[str, str]] = {
    # ---- hints for API error codes ------------------------------------------------------------
    "hint.UNAUTHORIZED": {
        "en": "Set IPHONEMIRROR_API_KEY (or `config --api-key`) to the key shown in iPhoneMirror > Developer tools > Automation API.",
        "vi": "Đặt IPHONEMIRROR_API_KEY (hoặc `config --api-key`) bằng khóa hiển thị trong iPhoneMirror > Developer tools > Automation API.",
        "zh": "请将 IPHONEMIRROR_API_KEY（或 `config --api-key`）设为 iPhoneMirror > Developer tools > Automation API 中显示的密钥。",
        "ja": "IPHONEMIRROR_API_KEY（または `config --api-key`）に iPhoneMirror > Developer tools > Automation API に表示されるキーを設定してください。",
        "ko": "IPHONEMIRROR_API_KEY(또는 `config --api-key`)를 iPhoneMirror > Developer tools > Automation API에 표시된 키로 설정하세요.",
    },
    "hint.FORBIDDEN": {
        "en": "The API key lacks a scope this command needs; create a key with all scopes.",
        "vi": "Khóa API thiếu quyền (scope) mà lệnh này cần; hãy tạo khóa có đủ mọi quyền.",
        "zh": "API 密钥缺少此命令所需的权限范围；请创建包含全部权限的密钥。",
        "ja": "API キーにこのコマンドに必要なスコープがありません。全スコープを持つキーを作成してください。",
        "ko": "API 키에 이 명령에 필요한 권한 범위가 없습니다. 모든 범위를 가진 키를 만드세요.",
    },
    "hint.DEVICE_NOT_FOUND": {
        "en": "Run `devices` and pass a valid --device id.",
        "vi": "Chạy `devices` rồi truyền --device với id hợp lệ.",
        "zh": "运行 `devices`，然后用 --device 传入有效的设备 id。",
        "ja": "`devices` を実行し、有効な --device id を指定してください。",
        "ko": "`devices`를 실행한 뒤 올바른 --device id를 지정하세요.",
    },
    "hint.DEVICE_NOT_CONNECTED": {
        "en": "The phone is not connected. Reconnect USB or AirPlay in iPhoneMirror, then run `doctor`.",
        "vi": "Điện thoại chưa kết nối. Kết nối lại USB hoặc AirPlay trong iPhoneMirror, rồi chạy `doctor`.",
        "zh": "手机未连接。请在 iPhoneMirror 中重新连接 USB 或 AirPlay，然后运行 `doctor`。",
        "ja": "iPhone が接続されていません。iPhoneMirror で USB または AirPlay を再接続し、`doctor` を実行してください。",
        "ko": "iPhone이 연결되어 있지 않습니다. iPhoneMirror에서 USB 또는 AirPlay를 다시 연결한 뒤 `doctor`를 실행하세요.",
    },
    "hint.DEVICE_NOT_READY": {
        "en": "Run `prepare`, then `doctor`.",
        "vi": "Chạy `prepare`, rồi `doctor`.",
        "zh": "先运行 `prepare`，再运行 `doctor`。",
        "ja": "`prepare` を実行してから `doctor` を実行してください。",
        "ko": "`prepare`를 실행한 다음 `doctor`를 실행하세요.",
    },
    "hint.SCREENSHOT_UNAVAILABLE": {
        "en": "No video frame yet. Run `prepare` (starts mirroring) and wait a few seconds.",
        "vi": "Chưa có khung hình. Chạy `prepare` (bắt đầu phản chiếu) và đợi vài giây.",
        "zh": "尚无视频帧。运行 `prepare`（开始镜像）并等待几秒。",
        "ja": "まだ映像フレームがありません。`prepare`（ミラーリング開始）を実行して数秒待ってください。",
        "ko": "아직 영상 프레임이 없습니다. `prepare`(미러링 시작)를 실행하고 몇 초 기다리세요.",
    },
    "hint.CONTROL_NOT_AVAILABLE": {
        "en": "Mirroring works but control does not. Set up a control path in iPhoneMirror (Bluetooth HID + AssistiveTouch, or the USB touch bridge). See references/setup.md.",
        "vi": "Phản chiếu hoạt động nhưng chưa điều khiển được. Hãy thiết lập kênh điều khiển trong iPhoneMirror (Bluetooth HID + AssistiveTouch, hoặc cầu cảm ứng USB). Xem references/setup.md.",
        "zh": "镜像正常但无法控制。请在 iPhoneMirror 中设置控制方式（蓝牙 HID + 辅助触控，或 USB 触控桥）。参见 references/setup.md。",
        "ja": "ミラーリングは動作していますが操作できません。iPhoneMirror で操作経路（Bluetooth HID + AssistiveTouch、または USB タッチブリッジ）を設定してください。references/setup.md を参照。",
        "ko": "미러링은 되지만 제어는 안 됩니다. iPhoneMirror에서 제어 경로(Bluetooth HID + AssistiveTouch 또는 USB 터치 브리지)를 설정하세요. references/setup.md 참고.",
    },
    "hint.CONTROL_LOCKED": {
        "en": "Another client holds the control lease. Close other automation, or wait for it to expire.",
        "vi": "Một ứng dụng khác đang giữ quyền điều khiển. Đóng công cụ tự động hóa khác hoặc đợi hết hạn.",
        "zh": "另一个客户端持有控制租约。请关闭其他自动化工具，或等待其过期。",
        "ja": "別のクライアントが操作リースを保持しています。他の自動化を閉じるか、期限切れを待ってください。",
        "ko": "다른 클라이언트가 제어 권한을 갖고 있습니다. 다른 자동화를 닫거나 만료될 때까지 기다리세요.",
    },
    "hint.CAPABILITY_NOT_SUPPORTED": {
        "en": "The current control path cannot do this (e.g. Bluetooth HID has no multi-touch).",
        "vi": "Kênh điều khiển hiện tại không làm được thao tác này (vd. Bluetooth HID không hỗ trợ đa điểm).",
        "zh": "当前控制方式不支持此操作（例如蓝牙 HID 不支持多点触控）。",
        "ja": "現在の操作経路ではこれはできません（例: Bluetooth HID はマルチタッチ非対応）。",
        "ko": "현재 제어 경로로는 할 수 없습니다(예: Bluetooth HID는 멀티터치 미지원).",
    },
    "hint.GEOMETRY_CHANGED": {
        "en": "The screen rotated or resized. Take a new `shot` before acting.",
        "vi": "Màn hình đã xoay hoặc đổi kích thước. Chụp `shot` mới trước khi thao tác.",
        "zh": "屏幕已旋转或尺寸改变。操作前请重新 `shot`。",
        "ja": "画面が回転またはサイズ変更されました。操作前に新しい `shot` を撮ってください。",
        "ko": "화면이 회전되었거나 크기가 바뀌었습니다. 조작 전에 새 `shot`을 찍으세요.",
    },
    "hint.INVALID_COORDINATE": {
        "en": "Coordinates are outside the screen. Read them off the latest `shot` image.",
        "vi": "Tọa độ nằm ngoài màn hình. Hãy đọc tọa độ từ ảnh `shot` mới nhất.",
        "zh": "坐标超出屏幕。请从最新的 `shot` 图像中读取坐标。",
        "ja": "座標が画面外です。最新の `shot` 画像から読み取ってください。",
        "ko": "좌표가 화면 밖입니다. 최신 `shot` 이미지에서 좌표를 읽으세요.",
    },
    "hint.RATE_LIMITED": {
        "en": "Too many requests; slow down.",
        "vi": "Quá nhiều yêu cầu; hãy chậm lại.",
        "zh": "请求过多，请放慢速度。",
        "ja": "リクエストが多すぎます。間隔を空けてください。",
        "ko": "요청이 너무 많습니다. 속도를 늦추세요.",
    },
    "hint.MANAGEMENT_BUSY": {
        "en": "iPhoneMirror is busy (driver/install task). Wait and retry.",
        "vi": "iPhoneMirror đang bận (cài driver/cài đặt). Đợi rồi thử lại.",
        "zh": "iPhoneMirror 正忙（驱动/安装任务）。请稍后重试。",
        "ja": "iPhoneMirror がビジーです（ドライバー/インストール処理中）。待ってから再試行してください。",
        "ko": "iPhoneMirror가 바쁩니다(드라이버/설치 작업). 잠시 후 다시 시도하세요.",
    },
    "hint.UNSUPPORTED_RUNTIME": {
        "en": "This iPhoneMirror build does not support that route. Update iPhoneMirror.",
        "vi": "Bản iPhoneMirror này không hỗ trợ chức năng đó. Hãy cập nhật iPhoneMirror.",
        "zh": "此 iPhoneMirror 版本不支持该接口。请更新 iPhoneMirror。",
        "ja": "この iPhoneMirror のビルドはその機能に対応していません。更新してください。",
        "ko": "이 iPhoneMirror 빌드는 해당 기능을 지원하지 않습니다. 업데이트하세요.",
    },
    "hint.UNREACHABLE": {
        "en": "Start iPhoneMirror and enable About > (click version 5x) > Developer tools > Automation API.",
        "vi": "Mở iPhoneMirror và bật About > (bấm số phiên bản 5 lần) > Developer tools > Automation API.",
        "zh": "启动 iPhoneMirror，并在 关于 >（点击版本号 5 次）> Developer tools > Automation API 中启用。",
        "ja": "iPhoneMirror を起動し、About >（バージョンを 5 回クリック）> Developer tools > Automation API を有効にしてください。",
        "ko": "iPhoneMirror를 실행하고 About > (버전 5번 클릭) > Developer tools > Automation API를 켜세요.",
    },

    # ---- errors ---------------------------------------------------------------------------------
    "err.read_file": {
        "en": "Cannot read {path}: {err}",
        "vi": "Không đọc được {path}: {err}",
        "zh": "无法读取 {path}：{err}",
        "ja": "{path} を読み込めません: {err}",
        "ko": "{path}을(를) 읽을 수 없습니다: {err}",
    },
    "err.unreachable": {
        "en": "Cannot reach iPhoneMirror at {base} ({reason}).",
        "vi": "Không kết nối được iPhoneMirror tại {base} ({reason}).",
        "zh": "无法连接到 {base} 上的 iPhoneMirror（{reason}）。",
        "ja": "{base} の iPhoneMirror に接続できません（{reason}）。",
        "ko": "{base}의 iPhoneMirror에 연결할 수 없습니다({reason}).",
    },
    "err.timeout": {
        "en": "Timed out talking to {url}.",
        "vi": "Hết thời gian chờ khi gọi {url}.",
        "zh": "与 {url} 通信超时。",
        "ja": "{url} との通信がタイムアウトしました。",
        "ko": "{url}와(과) 통신하는 중 시간이 초과되었습니다.",
    },
    "err.no_key": {
        "en": "No API key configured.",
        "vi": "Chưa cấu hình khóa API.",
        "zh": "未配置 API 密钥。",
        "ja": "API キーが設定されていません。",
        "ko": "API 키가 설정되지 않았습니다.",
    },
    "err.no_devices": {
        "en": "iPhoneMirror reports no devices. Connect the phone (USB or AirPlay).",
        "vi": "iPhoneMirror không thấy thiết bị nào. Hãy kết nối điện thoại (USB hoặc AirPlay).",
        "zh": "iPhoneMirror 未发现设备。请连接手机（USB 或 AirPlay）。",
        "ja": "iPhoneMirror にデバイスがありません。iPhone を接続してください（USB または AirPlay）。",
        "ko": "iPhoneMirror에 기기가 없습니다. iPhone을 연결하세요(USB 또는 AirPlay).",
    },
    "err.many_devices": {
        "en": "Several devices; pass --device <id> or set IPHONE_USE_DEVICE:\n{listing}",
        "vi": "Có nhiều thiết bị; truyền --device <id> hoặc đặt IPHONE_USE_DEVICE:\n{listing}",
        "zh": "有多台设备；请传入 --device <id> 或设置 IPHONE_USE_DEVICE：\n{listing}",
        "ja": "複数のデバイスがあります。--device <id> を指定するか IPHONE_USE_DEVICE を設定してください:\n{listing}",
        "ko": "기기가 여러 대입니다. --device <id>를 지정하거나 IPHONE_USE_DEVICE를 설정하세요:\n{listing}",
    },
    "err.not_png": {
        "en": "Screenshot is not a PNG.",
        "vi": "Ảnh chụp màn hình không phải PNG.",
        "zh": "截图不是 PNG 格式。",
        "ja": "スクリーンショットが PNG ではありません。",
        "ko": "스크린샷이 PNG가 아닙니다.",
    },
    "err.no_token": {
        "en": "iPhoneMirror did not return a control session token.",
        "vi": "iPhoneMirror không trả về mã phiên điều khiển.",
        "zh": "iPhoneMirror 未返回控制会话令牌。",
        "ja": "iPhoneMirror が操作セッショントークンを返しませんでした。",
        "ko": "iPhoneMirror가 제어 세션 토큰을 반환하지 않았습니다.",
    },
    "err.unknown_size": {
        "en": "Unknown screen size; take a `shot` first.",
        "vi": "Chưa biết kích thước màn hình; hãy chạy `shot` trước.",
        "zh": "屏幕尺寸未知；请先 `shot`。",
        "ja": "画面サイズが不明です。先に `shot` を撮ってください。",
        "ko": "화면 크기를 알 수 없습니다. 먼저 `shot`을 찍으세요.",
    },
    "err.no_shot": {
        "en": "No screenshot for this device yet. Run `shot` first and read coordinates off it.",
        "vi": "Chưa có ảnh chụp cho thiết bị này. Chạy `shot` trước và đọc tọa độ từ ảnh đó.",
        "zh": "此设备还没有截图。请先运行 `shot` 并从图中读取坐标。",
        "ja": "このデバイスのスクリーンショットがまだありません。先に `shot` を実行し、そこから座標を読み取ってください。",
        "ko": "이 기기의 스크린샷이 아직 없습니다. 먼저 `shot`을 실행하고 좌표를 읽으세요.",
    },
    "err.geometry": {
        "en": "Screen geometry changed ({old} -> {new}). Take a new `shot` before acting.",
        "vi": "Kích thước màn hình đã thay đổi ({old} -> {new}). Chụp `shot` mới trước khi thao tác.",
        "zh": "屏幕尺寸已改变（{old} -> {new}）。操作前请重新 `shot`。",
        "ja": "画面サイズが変わりました（{old} -> {new}）。操作前に新しい `shot` を撮ってください。",
        "ko": "화면 크기가 바뀌었습니다({old} -> {new}). 조작 전에 새 `shot`을 찍으세요.",
    },
    "err.outside": {
        "en": "({x}, {y}) is outside the screen (view is {w}x{h}).",
        "vi": "({x}, {y}) nằm ngoài màn hình (khung nhìn {w}x{h}).",
        "zh": "({x}, {y}) 超出屏幕（视图为 {w}x{h}）。",
        "ja": "({x}, {y}) は画面外です（ビューは {w}x{h}）。",
        "ko": "({x}, {y})는 화면 밖입니다(뷰 {w}x{h}).",
    },
    "err.zoom_pillow": {
        "en": "zoom needs Pillow (pip install pillow).",
        "vi": "zoom cần Pillow (pip install pillow).",
        "zh": "zoom 需要 Pillow（pip install pillow）。",
        "ja": "zoom には Pillow が必要です（pip install pillow）。",
        "ko": "zoom에는 Pillow가 필요합니다(pip install pillow).",
    },
    "err.zoom_no_shot": {
        "en": "No screenshot to zoom into. Run `shot` first.",
        "vi": "Không có ảnh để phóng to. Chạy `shot` trước.",
        "zh": "没有可放大的截图。请先运行 `shot`。",
        "ja": "拡大するスクリーンショットがありません。先に `shot` を実行してください。",
        "ko": "확대할 스크린샷이 없습니다. 먼저 `shot`을 실행하세요.",
    },
    "err.zoom_small": {
        "en": "Zoom region is too small; give two opposite corners in view coordinates.",
        "vi": "Vùng phóng to quá nhỏ; hãy đưa hai góc đối diện theo tọa độ khung nhìn.",
        "zh": "放大区域太小；请给出视图坐标中的两个对角点。",
        "ja": "拡大範囲が小さすぎます。ビュー座標で対角の 2 点を指定してください。",
        "ko": "확대 영역이 너무 작습니다. 뷰 좌표로 마주보는 두 모서리를 지정하세요.",
    },
    "err.amount": {
        "en": "--amount is a fraction of the screen height between 0.02 and 0.5.",
        "vi": "--amount là tỉ lệ chiều cao màn hình, từ 0.02 đến 0.5.",
        "zh": "--amount 是屏幕高度的比例，范围 0.02 到 0.5。",
        "ja": "--amount は画面高さの割合で、0.02〜0.5 の範囲です。",
        "ko": "--amount는 화면 높이의 비율로 0.02~0.5 사이입니다.",
    },
    "err.empty_text": {
        "en": "Empty text.",
        "vi": "Văn bản trống.",
        "zh": "文本为空。",
        "ja": "テキストが空です。",
        "ko": "텍스트가 비어 있습니다.",
    },
    "err.text_too_long": {
        "en": "Text exceeds 64 KiB.",
        "vi": "Văn bản vượt quá 64 KiB.",
        "zh": "文本超过 64 KiB。",
        "ja": "テキストが 64 KiB を超えています。",
        "ko": "텍스트가 64 KiB를 초과합니다.",
    },
    "err.prefix": {"en": "ERROR", "vi": "LỖI", "zh": "错误", "ja": "エラー", "ko": "오류"},
    "hint.prefix": {"en": "hint", "vi": "gợi ý", "zh": "提示", "ja": "ヒント", "ko": "힌트"},

    # ---- screenshots ----------------------------------------------------------------------------
    "shot.sizes": {
        "en": "view {vw}x{vh} (coordinates for tap/swipe), capture {cw}x{ch}",
        "vi": "view {vw}x{vh} (tọa độ dùng cho tap/swipe), capture {cw}x{ch}",
        "zh": "view {vw}x{vh}（tap/swipe 使用此坐标），capture {cw}x{ch}",
        "ja": "view {vw}x{vh}（tap/swipe はこの座標）、capture {cw}x{ch}",
        "ko": "view {vw}x{vh}(tap/swipe 좌표), capture {cw}x{ch}",
    },
    "shot.no_pillow": {
        "en": "Pillow not installed: image is full resolution, no grid (pip install pillow).",
        "vi": "Chưa cài Pillow: ảnh ở độ phân giải gốc, không có lưới (pip install pillow).",
        "zh": "未安装 Pillow：图像为原始分辨率且无网格（pip install pillow）。",
        "ja": "Pillow が未インストール: 画像はフル解像度でグリッドなし（pip install pillow）。",
        "ko": "Pillow 미설치: 원본 해상도, 격자 없음(pip install pillow).",
    },
    "zoom.info": {
        "en": "region view ({x1},{y1})-({x2},{y2}); grid labels are view coordinates - use them directly with tap.",
        "vi": "vùng view ({x1},{y1})-({x2},{y2}); nhãn lưới là tọa độ view - dùng trực tiếp với tap.",
        "zh": "区域 view ({x1},{y1})-({x2},{y2})；网格标签为视图坐标，可直接用于 tap。",
        "ja": "範囲 view ({x1},{y1})-({x2},{y2})。グリッドのラベルはビュー座標なので tap にそのまま使えます。",
        "ko": "영역 view ({x1},{y1})-({x2},{y2}); 격자 라벨은 뷰 좌표이므로 tap에 그대로 쓰세요.",
    },

    # ---- input ----------------------------------------------------------------------------------
    "sent": {
        "en": "sent: {msg}  (dispatched; verify on the next screenshot)",
        "vi": "đã gửi: {msg}  (đã phát lệnh; kiểm tra lại ở ảnh chụp tiếp theo)",
        "zh": "已发送：{msg}（仅表示已下发；请在下一张截图中确认）",
        "ja": "送信: {msg}（送出のみ。次のスクリーンショットで確認してください）",
        "ko": "전송: {msg}  (전달만 됨; 다음 스크린샷에서 확인하세요)",
    },
    "act.tap": {"en": "tap", "vi": "chạm", "zh": "点击", "ja": "タップ", "ko": "탭"},
    "act.double_tap": {"en": "double-tap", "vi": "chạm hai lần", "zh": "双击", "ja": "ダブルタップ", "ko": "더블 탭"},
    "act.long_press": {"en": "long-press", "vi": "nhấn giữ", "zh": "长按", "ja": "長押し", "ko": "길게 누르기"},
    "act.swipe": {"en": "swipe", "vi": "vuốt", "zh": "滑动", "ja": "スワイプ", "ko": "스와이프"},
    "act.scroll": {
        "en": "scroll {direction} {amount} of screen",
        "vi": "cuộn {direction} {amount} màn hình",
        "zh": "滚动 {direction}，屏幕的 {amount}",
        "ja": "スクロール {direction}（画面の {amount}）",
        "ko": "스크롤 {direction} (화면의 {amount})",
    },
    "act.home_gesture": {
        "en": "home gesture (swipe up from bottom edge)",
        "vi": "cử chỉ về Màn hình chính (vuốt lên từ cạnh dưới)",
        "zh": "主屏幕手势（从底部边缘上滑）",
        "ja": "ホームジェスチャー（下端から上にスワイプ）",
        "ko": "홈 제스처(아래 가장자리에서 위로 스와이프)",
    },
    "act.switcher": {
        "en": "app switcher gesture (swipe up and hold)",
        "vi": "cử chỉ trình chuyển ứng dụng (vuốt lên và giữ)",
        "zh": "应用切换器手势（上滑并停顿）",
        "ja": "Appスイッチャーのジェスチャー（上にスワイプして止める）",
        "ko": "앱 전환기 제스처(위로 스와이프 후 멈춤)",
    },
    "act.back": {
        "en": "back gesture (swipe right from left edge)",
        "vi": "cử chỉ quay lại (vuốt phải từ cạnh trái)",
        "zh": "返回手势（从左边缘右滑）",
        "ja": "戻るジェスチャー（左端から右にスワイプ）",
        "ko": "뒤로 제스처(왼쪽 가장자리에서 오른쪽으로 스와이프)",
    },
    "act.spotlight": {
        "en": "Spotlight gesture (swipe down on Home Screen)",
        "vi": "cử chỉ Spotlight (vuốt xuống trên Màn hình chính)",
        "zh": "Spotlight 手势（在主屏幕下滑）",
        "ja": "Spotlight ジェスチャー（ホーム画面で下にスワイプ）",
        "ko": "Spotlight 제스처(홈 화면에서 아래로 스와이프)",
    },
    "act.text": {
        "en": "text ({n} chars) via phone pasteboard - an 'Allow Paste' prompt may appear",
        "vi": "văn bản ({n} ký tự) qua bộ nhớ tạm của điện thoại - có thể xuất hiện hộp 'Cho phép dán'",
        "zh": "文本（{n} 个字符）经由手机剪贴板 - 可能会出现“允许粘贴”提示",
        "ja": "テキスト（{n} 文字）を iPhone のペーストボード経由で入力 - 「ペーストを許可」が出る場合があります",
        "ko": "텍스트({n}자)를 iPhone 클립보드로 입력 - '붙여넣기 허용' 알림이 나올 수 있음",
    },
    "err.capability": {
        "en": "This device's control path does not support `{action}`.",
        "vi": "Kênh điều khiển của thiết bị này không hỗ trợ `{action}`.",
        "zh": "此设备的控制方式不支持 `{action}`。",
        "ja": "このデバイスの操作経路は `{action}` に対応していません。",
        "ko": "이 기기의 제어 경로는 `{action}`을(를) 지원하지 않습니다.",
    },
    "act.launch": {
        "en": "launch {bundle}",
        "vi": "mở ứng dụng {bundle}",
        "zh": "启动 {bundle}",
        "ja": "{bundle} を起動",
        "ko": "{bundle} 실행",
    },
    "act.key": {"en": "key {name}", "vi": "phím {name}", "zh": "按键 {name}", "ja": "キー {name}", "ko": "키 {name}"},

    # ---- doctor ---------------------------------------------------------------------------------
    "doc.key_set": {"en": "API key: set", "vi": "Khóa API: đã đặt", "zh": "API 密钥：已设置", "ja": "API キー: 設定済み", "ko": "API 키: 설정됨"},
    "doc.key_missing": {"en": "API key: MISSING", "vi": "Khóa API: THIẾU", "zh": "API 密钥：缺失", "ja": "API キー: 未設定", "ko": "API 키: 없음"},
    "doc.app_ok": {
        "en": "iPhoneMirror: reachable, version {version}, apiRunning={api}, mainWindowVisible={win}",
        "vi": "iPhoneMirror: kết nối được, phiên bản {version}, apiRunning={api}, mainWindowVisible={win}",
        "zh": "iPhoneMirror：可连接，版本 {version}，apiRunning={api}，mainWindowVisible={win}",
        "ja": "iPhoneMirror: 接続可能、バージョン {version}、apiRunning={api}、mainWindowVisible={win}",
        "ko": "iPhoneMirror: 연결됨, 버전 {version}, apiRunning={api}, mainWindowVisible={win}",
    },
    "doc.app_bad": {
        "en": "iPhoneMirror: NOT OK - {err}",
        "vi": "iPhoneMirror: LỖI - {err}",
        "zh": "iPhoneMirror：异常 - {err}",
        "ja": "iPhoneMirror: 異常 - {err}",
        "ko": "iPhoneMirror: 문제 있음 - {err}",
    },
    "doc.devices_bad": {
        "en": "devices: NOT OK - {err}",
        "vi": "thiết bị: LỖI - {err}",
        "zh": "设备：异常 - {err}",
        "ja": "デバイス: 異常 - {err}",
        "ko": "기기: 문제 있음 - {err}",
    },
    "doc.no_devices": {
        "en": "devices: none. Connect the phone over USB (tap Trust) or start AirPlay Screen Mirroring to this PC.",
        "vi": "thiết bị: không có. Cắm điện thoại qua USB (chọn Tin cậy) hoặc bật Phản chiếu màn hình AirPlay tới PC này.",
        "zh": "设备：无。请用 USB 连接手机（点“信任”），或用 AirPlay 屏幕镜像到这台电脑。",
        "ja": "デバイス: なし。USB で接続（「信頼」をタップ）するか、AirPlay 画面ミラーリングでこの PC に接続してください。",
        "ko": "기기: 없음. USB로 연결(신뢰 탭)하거나 AirPlay 화면 미러링으로 이 PC에 연결하세요.",
    },
    "doc.device": {"en": "device", "vi": "thiết bị", "zh": "设备", "ja": "デバイス", "ko": "기기"},
    "doc.selected": {"en": "selected", "vi": "đã chọn", "zh": "已选择", "ja": "選択中", "ko": "선택됨"},
    "doc.not_capturing": {
        "en": "  -> not capturing: run `prepare`.",
        "vi": "  -> chưa ghi hình: chạy `prepare`.",
        "zh": "  -> 未在采集：运行 `prepare`。",
        "ja": "  -> キャプチャしていません: `prepare` を実行してください。",
        "ko": "  -> 캡처 중이 아님: `prepare`를 실행하세요.",
    },
    "doc.no_control": {
        "en": "  -> control not available: screenshots will work, input will not. See references/setup.md.",
        "vi": "  -> chưa điều khiển được: chụp màn hình được nhưng không thao tác được. Xem references/setup.md.",
        "zh": "  -> 控制不可用：可以截图，但无法输入。参见 references/setup.md。",
        "ja": "  -> 操作不可: スクリーンショットは可能ですが入力はできません。references/setup.md を参照。",
        "ko": "  -> 제어 불가: 스크린샷은 되지만 입력은 안 됩니다. references/setup.md 참고.",
    },
    "doc.no_pillow": {
        "en": "Pillow: missing (pip install pillow) - screenshots will be full size without a grid.",
        "vi": "Pillow: thiếu (pip install pillow) - ảnh chụp sẽ ở kích thước gốc, không có lưới.",
        "zh": "Pillow：缺失（pip install pillow）- 截图将为原始尺寸且无网格。",
        "ja": "Pillow: なし（pip install pillow）- スクリーンショットはフルサイズでグリッドなし。",
        "ko": "Pillow: 없음(pip install pillow) - 스크린샷이 원본 크기이며 격자가 없습니다.",
    },
    "doc.language": {"en": "language", "vi": "ngôn ngữ", "zh": "语言", "ja": "言語", "ko": "언어"},

    # ---- misc -----------------------------------------------------------------------------------
    "misc.no_devices": {"en": "no devices", "vi": "không có thiết bị", "zh": "无设备", "ja": "デバイスなし", "ko": "기기 없음"},
    "misc.clipboard_set": {
        "en": "clipboard set", "vi": "đã đặt bộ nhớ tạm", "zh": "已设置剪贴板", "ja": "クリップボードを設定しました", "ko": "클립보드 설정됨",
    },
    "misc.release_noop": {
        "en": "Leases are released after every command; nothing to do.",
        "vi": "Quyền điều khiển được trả lại sau mỗi lệnh; không cần làm gì.",
        "zh": "每条命令后都会释放租约，无需操作。",
        "ja": "リースは各コマンド後に解放されます。何もする必要はありません。",
        "ko": "제어 권한은 명령마다 해제됩니다. 할 일이 없습니다.",
    },
    "misc.saved": {"en": "saved {path}", "vi": "đã lưu {path}", "zh": "已保存 {path}", "ja": "{path} に保存しました", "ko": "{path}에 저장됨"},
    "misc.languages": {
        "en": "Available languages (use --lang CODE or IPHONE_USE_LANG):",
        "vi": "Ngôn ngữ hỗ trợ (dùng --lang MÃ hoặc IPHONE_USE_LANG):",
        "zh": "可用语言（使用 --lang 代码 或 IPHONE_USE_LANG）：",
        "ja": "利用可能な言語（--lang コード または IPHONE_USE_LANG）:",
        "ko": "사용 가능한 언어(--lang 코드 또는 IPHONE_USE_LANG):",
    },
}


def normalize(code: str | None) -> str | None:
    """'vi_VN', 'zh-Hans-CN', 'Japanese_Japan.932' -> 'vi' / 'zh' / 'ja'; unknown -> None."""
    if not code:
        return None
    c = code.strip().lower().replace("-", "_")
    if c in LANGUAGES:
        return c
    prefix = c.split("_")[0].split(".")[0]
    if prefix in LANGUAGES:
        return prefix
    names = {"english": "en", "vietnamese": "vi", "chinese": "zh", "japanese": "ja", "korean": "ko"}
    return names.get(prefix)


def detect() -> str:
    """Best guess at the user's UI language from the OS."""
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary = langid & 0x3FF
            found = {0x09: "en", 0x2A: "vi", 0x04: "zh", 0x11: "ja", 0x12: "ko"}.get(primary)
            if found:
                return found
        except (AttributeError, OSError):
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        found = normalize(os.environ.get(var))
        if found:
            return found
    try:
        found = normalize(locale.getlocale()[0])
        if found:
            return found
    except ValueError:
        pass
    return "en"


def set_language(*candidates: str | None) -> str:
    """Use the first valid candidate, else OS detection."""
    global _current
    for cand in candidates:
        found = normalize(cand)
        if found:
            _current = found
            return _current
    _current = detect()
    return _current


def current() -> str:
    return _current


def t(key: str, **kw) -> str:
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(_current) or entry["en"]
    return text.format(**kw) if kw else text


def has(key: str) -> bool:
    return key in MESSAGES
