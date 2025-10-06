# Makefile for Python Project

# Declare phony targets (targets that don't correspond to actual files)
.PHONY: clean

install:
	@echo "Setting up the Python environment..."
	pip install  .

clean:
	rm -rf __pycache__/ build *.egg-info
