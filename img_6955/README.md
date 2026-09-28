# IMG_6955 — 写真投影を使わない港の再現

Blender 5.2.2 LTS / Python 3 + Pillow。外部アドオン不要。
元写真は構図・色調を比較する参考資料です。モデル、材質、空、合成には貼り付けません。
形状はメートル単位の推定モデルです。近景を優先し、遠景と画面外は簡略化しています。
Unity 対応・書き出し・ベイクは今回の対象外です。

## 実行

リポジトリ直下で実行してください。各処理は個別に再実行できます。

```bash
cd /home/maya0513/workspace/blender-playgroud
python3 img_6955/scripts/run.py build
python3 img_6955/scripts/run.py validate
python3 img_6955/scripts/run.py preview --views clay
python3 img_6955/scripts/run.py preview
python3 img_6955/scripts/run.py final
python3 img_6955/scripts/run.py verify
```

- `build`：モデルを再構築して `.blend` を更新。以前の画像は残るため最新性は検証結果で確認します。
- `validate`：接地、接続、閉じた形状、階段、通路、写真投影の不使用を検査。
- `preview`：8視点。`--views photo shelter` のように選択して再実行可能。
- `final`：最新の構造検証と写真視点プレビューが必要。3024×3024pxを出力。
- `verify`：8枚の確認画像と完成画像の寸法、設定、ハッシュ、最新性を検査。
- 同時実行はロックで防止。CPU 16スレッドが既定。負荷を下げるなら各コマンドに `--threads 8` を指定。

## 長時間処理・再開

```bash
# 別ターミナルから進捗を確認（Ctrl+Cでログ表示だけ終了）
tail -f img_6955/review/logs/final.log
```

会話を閉じても手元で継続させる場合：

```bash
nohup python3 img_6955/scripts/run.py final > /tmp/img_6955-final-console.log 2>&1 &
```

再起動・中断した場合は、実行中のプロセスがないことを確認して同じコマンドを再実行してください。
ビルド・検証・プレビューが終わっていれば `final` から再開できます。
プレビューは成功した視点ごとに保存されるため、失敗した視点を `--views` で指定できます。
途中停止した1枚のレンダリング自体は最初からやり直します。
成功した画像だけを置換し、描画中の失敗では以前の画像を保持します。
レンダリングは保存済み `.blend` を変更しません。

## 出力と品質

- `hamamachi_breakwater.blend`：編集可能なシーン。
- `renders/hamamachi_breakwater.png`：3024×3024px、RGB PNG。
- `renders/` 内の別画像は保持し、検証レポートの `additional_unverified_files` に記録。今回の成果物9枚には含めません。
- `review/images/`：写真視点1512px、単色756px、その他1280×850px。
- `review/reports/`：構造・画像検証、処理時間、シーンと画像のSHA-256、描画設定。
- `review/logs/`：処理別ログ。再実行で同名ログを更新。

Cycles / CPU / AgX / sRGB。確認画像32～64サンプル、本番最大256サンプル、
適応サンプリング閾値0.01、OpenImageDenoise（Albedo + Normal）。
実際の時間は `preview.json` と `final.json` を参照してください。
写真投影ありの旧レンダリング時間は目安にしません。

写真との画素一致を合否基準にしません。構図・材質・空と海の印象は写真と並べて目視確認します。
自動検査のPASSは写真との一致やUnityでの動作を保証するものではありません。

## 今回の形状修正（revision 4）

- 広場のベンチは背もたれなし。座面の長辺を近くの海沿いの岸壁に平行に配置。
- 雑草は土台を使わず、コンクリートと縁石の狭い接合部から斜めに伸びる曲がった葉で生成。
- 左奥は左側を壁で切った扇形の10段。蹴上げ18cm・踏面32cm、3方向の歩行経路で検査。金属製の手すり・支柱は撤去し、コンクリートの側壁は維持。
- 左岸壁はコンクリート壁82cm、白い横棒の中心112cm。短い青い支柱と太いコンクリート柱を配置し、横棒は1本に変更。高さは写真からの推定値。
- 右の建物はトイレ。入口を真上から時計回りに90度移し、広場側の壁へ配置。
- 新しい入口の反対側の壁と、隣接する岸壁の外面を同一直線上に配置。基壇も境界内に納める。
- トイレ内の設備は省略。元写真への投影は使用しない。

最初に `build` と `validate` を実行し、`preview --views clay photo pavilion overview` で
修正形状を確認できます。その後 `preview` で全8視点、`final` と `verify` で本番と検証を更新します。
画像・ログ・実測結果は今回のシーンのハッシュに対応するものを参照してください。

## 今回の実測結果（2026-09-28）

左階段の手すり撤去と左岸壁の比率修正を反映済み。CPU 16スレッドで、
確認画像8枚の描画は合計 172.9 秒、本番3024pxは 383.3 秒でした（起動処理等を除く）。
接続 1070 箇所、6本の歩行経路、写真投影不使用、全9成果物の寸法・設定・ハッシュ検証はPASS。
別途存在する `renders/ferry.png` は保持し、今回の検証済み成果物には含めていません。

## 制作に適用した資料

- [Blender：カメラと画角](https://docs.blender.org/UATEST/manual/en/dev/render/cameras.html)：細部より先に構図と遠近感を調整。
- [Bump](https://docs.blender.org/UATEST/manual/en/dev/render/shader_nodes/displacement/bump.html)：細かな凹凸は法線、輪郭は形状。
- [Noise](https://docs.blender.org/UATEST/manual/en/dev/render/shader_nodes/textures/noise.html)：複数スケールの模様と制限したDetail。
- [Sampling](https://docs.blender.org/UATEST/manual/en/dev/render/cycles/render_settings/sampling.html)：適応サンプリングとAlbedo + Normalを利用したノイズ除去。
- [Color Management](https://docs.blender.org/manual/ja/5.2/render/color_management/index.html)：線形の材質値と表示色空間を区別。
