.PHONY: install data train test demo server eval sim agents
install:  ; pip install -r requirements.txt
data:     ; python -m scripts.generate_synthetic_data --per-scenario 24 && python -m scripts.generate_synthetic_data --extra-test 20
train:    ; python -m scripts.train_models
test:     ; python -m pytest -q
agents:   ; python -m scripts.run_agents
demo:     ; python -m scripts.run_pipeline --video data/raw/videos/demo_accident_tbone.mp4 --auto-approve
server:   ; python -m scripts.run_server
eval:     ; python -m scripts.run_evaluation
sim:      ; python -m scripts.run_sumo_experiments
