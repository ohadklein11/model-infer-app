# Model Inference Service

*By Ohad Klein*

A ML inference platform built with FastAPI, MongoDB, and Kafka. Submit jobs to run Hugging Face models, track their status, and retrieve results through a REST API and web interface.

## Quick Start

```bash
git clone <repository-url>
cd model-infer-app
make up
```
Example command - query VQA:
```
curl -s -X POST http://localhost:8092/predict -H "Content-Type: application/json" -d '{"imageUrl":"https://picsum.photos/200","question":"What is in the image?"}'
```
