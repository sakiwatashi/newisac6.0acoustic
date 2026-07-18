# D4 風險

| ID | 風險 | 緩解 | 狀態 |
|----|------|------|------|
| R1 | Robotiq 摩擦仍抬不起 | g0；調 friction/質量/步長；Franka 對照 | open |
| R2 | GMO 過慢，PPO 難訓 | 降 capture 頻率；特徵緩存；先 1-DOF | open |
| R3 | 近場無聲學 | 狀態機終端開環；獎勵分階段 | open |
| R4 | 與 D3 敘事混淆 | v2_d4 目錄；handoff 明示 | mitigated |
| R5 | 雙棧（Sim runner vs Lab）漂移 | 共用校正 JSON 與 factory | open |
| R6 | weld fallback 被誤寫成主結果 | 分析器分欄；論文禁詞 | open |
