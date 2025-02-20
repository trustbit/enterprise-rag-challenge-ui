HOST_DIR=/var/lib/rag-api
SERVICE=rag-api.service

.PHONY: sync
sync:
	rsync -avz --exclude='venv/' --exclude=".*" --exclude="run.sh" --exclude='tmp/' --rsync-path="sudo rsync" . $(HOST):$(HOST_DIR)

.PHONY: install
install:
	ssh -t $(HOST) "cd $(HOST_DIR) && \
		python3 -m venv venv && \
		. venv/bin/activate && \
		pip install -r requirements.txt && \
		sudo systemctl enable $(HOST_DIR)/$(SERVICE)"

.PHONY: stop
stop:
	ssh -t $(HOST) sudo systemctl stop $(SERVICE)

.PHONY: start
start:
	ssh -t $(HOST) "sudo systemctl daemon-reload && sudo systemctl start $(SERVICE)"


.PHONY: logs
logs:
	ssh -t $(HOST) sudo journalctl -u $(SERVICE) -f

.PHONY: deploy
deploy: stop sync start logs





