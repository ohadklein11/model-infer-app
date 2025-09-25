#!/bin/bash
set -e

echo "Waiting for Kafka to be ready..."
# Wait for Kafka to be available
until kafka-topics --bootstrap-server kafka:9092 --list &>/dev/null; do
    echo "Kafka is not ready yet. Waiting..."
    sleep 2
done

echo "Kafka is ready. Creating topics..."

# Create the three required topics
kafka-topics --create --if-not-exists --topic inference.jobs.request --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
kafka-topics --create --if-not-exists --topic inference.jobs.started --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
kafka-topics --create --if-not-exists --topic inference.jobs.result --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1

echo "Topics created successfully:"
kafka-topics --list --bootstrap-server kafka:9092

echo "Kafka initialization complete!"
