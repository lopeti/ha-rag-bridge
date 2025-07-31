# HA RAG Bridge

## Purpose

Define the main purpose of this project.

## Target Users

Describe who will use this.


## Project Summary

Home Assistant RAG (Retrieval-Augmented Generation) bridge that syncs Home Assistant metadata into ArangoDB and provides FastAPI services for semantic search and knowledge retrieval



## Goals

- Sync Home Assistant metadata to ArangoDB
- Provide semantic search capabilities over HA data
- Enable RAG-based querying of Home Assistant information
- Support multiple embedding backends (local, OpenAI, Gemini)
- Offer RESTful API for accessing processed HA data



## Constraints

- Requires ArangoDB 3.11+ with experimental vector index support
- Python 3.13.2+ required
- Need access to Home Assistant instance
- Rust toolchain needed for pydantic-core building



## Stakeholders

- Home Assistant users
- Smart home developers
- Data analysts working with IoT data
- Developers building HA integrations

