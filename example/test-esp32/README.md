# ESP32 Lチカ

ELEGOO ESP-32 USB-C（CP2102搭載、30ピン）を想定した最小のArduinoサンプルです。
GPIO2をHIGHで0.5秒、LOWで0.5秒に切り替えます。

## 構成

- `platformio.ini`: `esp32dev` ボード、Arduinoフレームワーク、ESP32プラットフォーム8.0.0。
- `src/main.cpp`: GPIO2の点滅処理。
- `.pio/`: ビルド時の生成物。Gitには含めません。

Pixiはワークスペースのルートにある共通環境を使います。このフォルダに別のPython環境を作る必要はありません。
ESP32用ツールチェーンとArduinoフレームワークはPlatformIOが初回ビルド時に取得します。これらは`pixi.lock`ではなくPlatformIO側で管理されます。

## 0. 開発環境の導入（Windows）

### PixiとPlatformIO

Pixiが未導入の場合は、[Pixi公式のWindowsインストーラー](https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-pc-windows-msvc.msi)で導入し、ターミナルを開き直します。

ワークスペースのルート（`pixi.toml`と`pixi.lock`があるフォルダ）でPowerShellを開き、次を実行します。

```powershell
pixi --version
pixi install --locked
pixi run --locked pio --version
```

このリポジトリにはPlatformIOの依存設定を追加済みです。Python、PlatformIO、Arduino IDEを別々にインストールする必要はありません。初回の環境構築とビルドにはインターネット接続が必要です。

## 1. ビルド

ワークスペースのルートでPowerShellまたはターミナルを開き、実行します。

```powershell
pixi run --locked pio run -d example/test-esp32
```

最後に`SUCCESS`と表示されればビルド成功です。USB接続なしでも実行できます。

## 2. USB接続とドライバー

1. 基板をデータ通信対応のUSBケーブルでPCにつなぎます。
2. WindowsのデバイスマネージャーでCP2102に警告がある場合は、次の手順でドライバーを導入します。
   1. [Silicon Labs公式ページのDownloads](https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers?tab=downloads)をブラウザーで開き、**CP210x Universal Windows Driver**をダウンロードします。今回取得したバージョンは11.6.0です。
   2. `CP210x_Universal_Windows_Driver.zip`を右クリックして「すべて展開」します。ZIPの中から直接実行しないでください。
   3. 展開先の`silabser.inf`を右クリックし、「インストール」を選びます。Windows 11で見当たらない場合は「その他のオプションを確認」も開きます。このパッケージにEXEインストーラーはありません。
   4. ドライバーの導入には管理者権限が必要です。管理者権限の確認（UAC）に応じて承認または管理者の認証を行います。
   5. デバイスマネージャーの「ポート（COMとLPT）」に、警告のない`Silicon Labs CP210x USB to UART Bridge (COM番号)`が表示されることを確認します。
3. 次のコマンドで基板のCOMポートを確認します。

```powershell
pixi run --locked pio device list
```

基板が表示されない間は書き込めません。シリアルモニターなど、そのCOMポートを使用中のアプリは閉じてください。

## 3. 書き込み

**基板上の既存プログラムはLチカに置き換わります。**
次の`COM3`は例です。上で確認した基板のポート名に置き換えて実行します。

```powershell
pixi run --locked pio run -d example/test-esp32 -t upload --upload-port COM3
```

接続待ちで止まる場合は、基板のBOOTボタンを押したまま書き込みを開始し、接続できたら離してください。
書き込み後に起動しない場合はEN（リセット）ボタンを押します。

## 4. 点滅の確認

基板のGPIO2につながったLEDが、0.5秒ごとに点灯・消灯すれば完了です。
電源表示用LEDが点灯したままでも、それ自体は異常ではありません。

[メーカーのESP32作例](https://wiki.elegoo.com/en/oshw-getting-started-%26-kits/dualboard-esp32)はLEDにGPIO2を使用しています。今回のELEGOO ESP-32 USB-C基板でも、GPIO2で内蔵LEDの点滅を確認しました。
書き込みに成功しても点滅しない場合は、基板の型番・回路図で制御可能な内蔵LEDの有無とピン番号を確認してください。GPIO2の出力が切り替わることと、内蔵LEDが点滅することは別の確認です。

GPIOは3.3V系です。GPIOに5Vを直接接続しないでください。外付けLEDを使う場合は必ず直列抵抗を入れ、電源を外してから配線してください。

## 確認済みの範囲

Windowsで`pixi run --locked pio run -d example/test-esp32`を実行し、`SUCCESS`を確認しました。
ESP32プラットフォーム8.0.0、Arduino ESP32 3.3.12で`example/test-esp32/.pio/build/esp32dev/firmware.bin`を生成済みです。
接続したESP32-D0WD-V3（revision v3.1）への書き込みとハッシュ検証に成功し、自動リセットまで完了しました。基板上のLEDが点滅することも、ユーザーの目視で確認済みです。
