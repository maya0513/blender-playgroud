# 平面ステンドグラス

完成モデル：[butterfly_flat.blend](butterfly_flat.blend)  
完成画像：[2048×2048](renders/final.png)  
確認資料：[参考との比較](review/images/comparison.png)・[各視点](review/images/views.png)  
検証結果：[verification.json](review/reports/verification.json)

## 再生成

Linux、Blender 5.2.2、Python 3、Pillow、DejaVu Sansが必要です。追加のBlenderアドオンは使いません。

```sh
/usr/bin/python3 scripts/run.py all
```

ワークスペースのルートからは次のコマンドを使います。

```sh
/usr/bin/python3 stained_glass_butterfly_flat/scripts/run.py all
```

`build` → `validate` → `preview` → `final` → `verify` の順で実行します。
単工程は `all` を工程名に置き換えます。`preview --views main` は主構図だけの確認、
`--threads 8` はCPUスレッド数の変更です。最終描画前に現行シーンの全確認視点が必要です。

描画はCycles CPU、確認1024角・64サンプル、完成2048角・512サンプル、Standard（図案の配色を保持）、
最大16バウンス・透過12バウンス、適応サンプリングとOpenImageDenoiseを使います。
バックグラウンド実行の音声環境はスクリプトが設定します。

## 編集

色ガラス・縁取り・装飾・撮影環境をコレクションごとに分けています。
ガラスと縁取りはメッシュで保持し、抽出輪郭もベジェカーブとして保存しています。
参考画像は `.blend` にパックされ、`Reference_Guides` 内で描画・表示を隠しています。
カメラは main・oblique。完成画像のカメラは `Camera · main` です。
全体高さは相対比率で約30 cmに設定しています。

`Editable_Contours` には抽出したベジェ輪郭を保持しています。
画像座標から各ガラス区画を作り、約2 mmの厚みを付けています。
色の吸収を区画ごとに調整し、背後の白い照明面で図案の配色を見せています。
元画像の連続的な色の勾配は区画ごとの代表色で、細かなきらめきは微粒子で近似しています。
輪郭を編集した場合は曲線からメッシュへ再変換して厚みを更新してください。
点で接する一部の輪郭は0.16 mm精度で閉じた体積に補正しています。
白い背景は撮影環境です。額・支持板は追加していません。

## 確認資料

`review/logs/` に工程ログ、`review/reports/` に形状・参照の整合性と描画条件を保存します。
検証では閉じた体積、外向きの法線、ガラス区画の厚みも確認します。
全確認視点が揃うと `preview_comparison.png` と `views.png` を作成します。
出力ファイル名は固定で、再実行で更新します。描画成功後に画像を置換し、検証では
シーンと画像のSHA-256を照合します。カメラ・材質を変更した場合は保存後に
`validate`、`preview`、`final`、`verify` を順に実行してください。
