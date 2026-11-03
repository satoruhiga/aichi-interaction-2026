# Day 1: 顔解析の JSON 受信

初回は workspace で `pixi run --locked python scripts/download_models.py` を実行し、共通モデルを取得します。

1. `day1.toe` を開き、動画を Spout 名 `TDSyphonSpoutOut` で送信します。
2. `RUN.cmd` をダブルクリックします。
3. TD の `/project1/websocket1` で最新の JSON、`json2` で特徴点のテーブルを確認します。

Python のウィンドウを閉じるか Esc を押すと終了します。
Python を再起動した後に受信が再開しなければ、`/project1/websocket1` の Active を一度オフにしてオンにします。

共通モデルは `../models/face_landmarker.task`。WebSocket は同じ PC の `127.0.0.1:8765` です。
AI が起動する場合は workspace で `pixi run --locked python -m day1.main` を実行します。
`--faces 2` で最大2人を解析できます。

## JSON

1メッセージが1回の解析結果です。`type`、単調増加の `timestamp_ms`、画像サイズ `image`、顔の配列 `faces` を送ります。
各顔の `landmarks` は `{x, y, z}` の配列です。顔番号は `faces` の添字、特徴点番号（0〜477）は `landmarks` の添字で表し、番号フィールドを重複して送りません。顔がない場合は `faces: []` を送ります。
X・Y は左下原点の UV 座標として送ります。`x` は元の値、`y = 1 - 元のy` で、両軸とも画像内は0〜1です。`z` は MediaPipe Face Landmarker の相対的な奥行きの出力であり、実距離ではありません。送信側では縦横比補正を行いません。座標の上下反転と Spout 受信画像の反転設定は別の処理です。
顔の配列順は人物の永続 ID ではありません。

Python のプレビューは受信映像です。

## 顔の特徴点

この教材は固定順の478点を省略せずに送ります。虹彩中心は点番号468・473です。最初の顔のそれぞれの位置は `$.faces[0].landmarks[468]`、`$.faces[0].landmarks[473]` で選べます。ほかの解析器に同じ番号を適用するものではありません。

番号の出典：[MediaPipe の公式グラフ](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_landmark/tensors_to_face_landmarks_with_attention.pbtxt)。

受信・JSONPath・表やCHOPへの変換は [Python から TouchDesigner へデータを渡す](../docs/python-to-touchdesigner.md)、表示位置への変換は [座標変換のノウハウ](../docs/coordinates.md) を参照してください。
