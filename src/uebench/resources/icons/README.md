# 本地 SVG 图标

本轮首页和导航动作图形来源：青舟中央 UI 候选
`e1486fb20c1dda33b7344ca860ff8f303c2183ee` 的
`docs/ui/assets/icons.svg`（候选尚未合并，不称已发布）。
原 sprite SHA256：`ae20eb19ff20f2a41c53ac840f89426afc13fa19f1a3fd81d978b300989d897c`。

对应关系：home→home、standards→book、new→plus、records→records、
excel→excel、factors→library、settings→settings、back→back。
保留 24×24 viewBox、path 几何与 1.7 stroke，仅拆为独立 SVG 并替换颜色。
`*-white.svg` 用于深色任务卡；Qt SVG icon engine / QPainter 按 DIP 绘制，
不先栅格化成固定物理像素。radio 图标保留本产品原有资源。
