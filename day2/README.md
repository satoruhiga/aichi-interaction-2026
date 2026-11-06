# Day 2: MediaPipeとTouchDesigner

1. `day2.toe` を開きます。
2. 顔は `RUN_FACE.cmd`、手は `RUN_HAND.cmd`、体は `RUN_POSE.cmd` をダブルクリックします。複数を同時に起動できます。macOS では下にある手動実行のコマンドを使います。
3. 終了はPythonのプレビューで Esc、またはコンソールで Ctrl+C を押します。

| 起動ファイル | TDのサンプル |
|---|---|
| RUN_FACE.cmd | TRACKING / BLENDSHAPE / FACE_LANDMARK |
| RUN_HAND.cmd | HAND |
| RUN_POSE.cmd | POSE |

## 配置

- `scripts/`：顔・手・体のPython、共通処理、TDコールバック。
- `media/`：動画・画像素材。
- `mesh/`：顔のメッシュ。
- `tox/`：TDコンポーネント。

`.cmd` はワークスペース共通のPixi環境を使います。手動実行はワークスペースのルートで行います。

```powershell
pixi run --locked python -m day2.scripts.face
pixi run --locked python -m day2.scripts.hand
pixi run --locked python -m day2.scripts.pose
```

モデルがない場合は、ルートで `pixi run --locked python scripts/download_models.py` を実行します。

## 映像と受信

TDの `/project1/VIDEO` を表示と解析の基準にします。PythonはSpout（macOSではSyphon）の `TDSyphonSpoutOut` を640×360で受け取り、解析結果をTDのWebSocketサーバー（ポート8765）へ送ります。

Pythonには `--sender TDSyphonSpoutOut`、`--port 8765`、`--hidden`、`--seconds 10` を指定できます。

`RECEIVER/INPUT_MSGS` は `type / message / received_ms` の表です。各サンプルの `MSG_SELECT` のMessage Typeで種類を指定します。`current_message` は更新から2秒を過ぎたデータを空データに切り替えます。

| type | データ | 検出上限 |
|---|---|---|
| face_landmarks | faces：landmarks、blendshapes | 顔1つ |
| hand_landmarks | hands：landmarks、handedness、score | 手4つ |
| pose_landmarks | poses：landmarks（visibility、presenceを含む） | 体1つ |

座標のx・yは左下原点の0〜1、zはMediaPipeの値です。2D表示用のアスペクト補正とZの平坦化はTD側で行います。

## 顔の選択と変換

顔の3サンプルでは、JSON DAT `json1` のFilter `$.faces[0]` で最初の顔を選びます。Python側の検出上限も増やして複数の顔を送る場合、`$.faces[1]` で2番目を選べます。

後段のScript DAT `face_table` は、選択した顔を既存の表形式へ変換します。コールバックは `scripts/face_table_callbacks.py` と同期しています。`day2.toe` と `scripts/` は一緒に置いてください。

`scripts/receiver_callbacks.py` は受信コールバックのソースです。TD内の受信コールバックは埋め込みで使用しています。

コンポーネントを別のTDファイルへ取り込む場合は、`RECEIVER`（Global OP Shortcut: RECEIVER）、`/project1/VIDEO`、必要な素材とコールバックファイルも用意します。
