# Thesis notes
**Title:** A Multi-Stage Computer Vision and Multi-Agent AI Framework for Real-Time Accident Detection and Intelligent Traffic Clearance.
**Contributions:** (1) closed loop detection -> verification -> severity -> dispatch -> diversion/signal plan -> simulation with human gate;
(2) two-stage verification (temporal evidence + classifier + VLM) evaluated against a rules-only baseline (ablation table);
(3) right tool per layer (LLM only for language, measured by latency/accuracy); (4) measured clearance impact vs fixed-time baseline.
**Chapters map:** Ch3 architecture = docs/agent_design.md + state_machine.md; Ch4 methodology = pipeline/, workers/; Ch5 experiments = eval/reports/;
Ch6 limitations = docs/limitations.md. Cite DoTA, CADP, DAD, CCD, UA-DETRAC, ByteTrack, YOLOv8, SUMO, IDM, LangGraph.
