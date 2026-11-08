# Day 3: 音声と画像を言葉で扱う

`day3.toe` を開き、使うサンプルの `.cmd` をダブルクリックします。両方を同時に起動できます。初回はそのスクリプトが必要なモデルをダウンロードします。

| 起動ファイル | 内容 |
|---|---|
| `RUN_SPEECH.cmd` | マイクの音声認識と、文字の読み上げ |
| `RUN_LFM3.cmd` | TD の映像について質問し、文章で回答を受け取る |

## 音声

音声認識と合成は speech.cpp 0.10.1 で動かします。認識は ReazonSpeech nemo v2（Q8_0）と Silero VAD、合成は Qwen3-TTS 0.6B CustomVoice（Q8_0）です。初回はモデル約1.88GBと実行ファイルを自動取得し、SHA256を確認します。WindowsはVulkan対応のGPUドライバーを使い、CUDA Toolkitやビルド環境は不要です。

- `speech` COMP の `Text` に文章を入力し、`Send` を押すと読み上げます。
- `Voice` は声の名前を選ぶメニューです。既定は日本語の `ono_anna`。他の声は主に他言語向けです。話速変更には対応していません。
- `Stop` で生成・再生と待機中の読み上げを中断します。
- 読み上げ中はマイク認識を停止し、終了後に再開します。読み上げに割り込んで話す用途には対応していません。
- COMP の DAT 出力には `speech_text`（認識文字）と `speech_status`（読み上げ状態、失敗時は `error`）が出ます。

合成モデルは起動時に読み込み、生成した音声をWAV保存せず順次スピーカーへ再生します。初回のGPU準備には時間がかかります。認識はCPUで動き、マイクはspeech.cppがOSの既定デバイスを直接開きます。マイクを変更する場合はOSで既定入力を変更し、サンプルを再起動してください。

スピーカーを調べる場合は `pixi run --locked python -m day3.scripts.speech --list-devices` を実行します。`--output-device` で番号または名前を指定できます。終了は起動したコンソールで Ctrl+C です。

## LFM3

LFM3-VL-2B の Q4_K_M 版と、画像用の Q8_0 projector を使います。

1. 使用する映像TOPを `VIDEO` に接続します。`VIDEO` → `syphonspoutout1` から、`TDSyphonSpoutOut` という名前でPythonに送ります。
2. `vl` COMP の `Question` に質問を書き、`Ask` を押します。
3. 押した時点でPythonが受信している直近の画像に対する回答が、1番目のDAT出力（Answer）に出ます。毎フレームの自動判定ではありません。

2番目のDAT出力（Status）はJSONです。`state` は `ready` / `thinking` / `error`、エラー時の詳細は `error` にあります。回答中の追加クリックは受け付けません。質問を変えて再度押すと、新しい画像について回答します。回答の正しさは実際の画像と比べて確認してください。

`decision_*` と `msg_decision` は別モデルd1の判定試作で、このVLの回答には使いません。VLは画像について文章で回答し、d1は指定した選択肢への判定・確率を返す用途です。

Python が `llama-server` を起動し、終了時に自分が起動したサーバーを停止します。既定の内部ポートは8093です。使用中の場合は起動せず、`--llama-port` で変更できます。ログは `.local/lfm3-server.log` に出ます。終了はプレビューで Esc、またはコンソールで Ctrl+C です。

## 接続状態と処理時間

`speech` と `vl` のカスタムパラメーター `Status` ページで、`Connection` と `Error` を確認できます。各Pythonに1秒間隔で応答確認を送り、5秒間応答がなければ `no_response` と表示します。未起動・切断・応答停止のどれかは通信だけでは区別できません。モデルのダウンロード・初期化中も、準備が終わるまでは応答しません。接続回復後は自動で `connected` に戻ります。推論や入力のエラーは `Error` に表示します。

処理結果にはミリ秒単位の計測値が含まれます。モデル読み込み時間とTDとの通信時間は含みません。

- VLの `lfm3_text` と完了時の `lfm3_status`：`generation_ms`（画像エンコードとローカル推論APIの応答を含む、生成処理全体）。
- 音声の完了時の `speech_status`：`first_audio_ms`（最初の音声データまで）、`generation_ms`（生成終了まで）、`playback_complete_ms`（スピーカーへの再生完了まで）。いずれも合成リクエスト送信時点からの時間です。最初のデータには無音が含まれる場合があり、発声開始時間とは異なります。
- 音声の `cancelled` が `true` の場合は中断までの計測値です。

回答・状態の出力は最新値を保持するため、古い `ready` だけで現在の接続状態を判断せず、`Connection` を確認してください。

## Python と TD の接続

TD の `RECEIVER` がポート8765で待ち受け、Python が接続します。TD からの操作は全クライアントに送信し、それぞれ自分の `type` だけ処理します。

| 方向 | type | 主なフィールド |
|---|---|---|
| TD → 音声 | `speak` | `text`, `voice`（声の名前、省略時は `ono_anna`） |
| TD → 音声 | `stop` | なし |
| 音声 → TD | `speech_text` | `text`, `timestamp_ms` |
| 音声 → TD | `speech_status` | `speaking`, `timestamp_ms`, 失敗時は `error` |
| TD → LFM3 | `lfm3_ask` | `text` |
| LFM3 → TD | `lfm3_text` | `text`, `question`, `timestamp_ms` |
| LFM3 → TD | `lfm3_status` | `state`, エラー時は `error` |

回答や認識文字は最新の結果として保持します。切断後も表示が残るため、表示されているだけで処理が動いているとは判断しないでください。全発話を記録する用途では、最新値だけを保持する共通送信部とは別に記録処理が必要です。

macOS ではワークスペースのルートから、次のように起動します。

```sh
pixi run --locked python -m day3.scripts.speech
pixi run --locked python -m day3.scripts.lfm3
```

モデルの URL・保存先・SHA256 は各 Python スクリプトにあります。モデル本体は共通の `models/` に保存し、Git には含めません。
