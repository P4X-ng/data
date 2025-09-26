#!/bin/bash

# Define the volume name (replace this with your actual volume name)
VOLUME_NAME="hgv0"

# Update the performance settings
echo "Updating performance settings for Gluster volume: $VOLUME_NAME"

# Set client I/O threads to improve performance in environments with high concurrency.
gluster volume set $VOLUME_NAME performance.client-io-threads on

# Enable read-ahead to improve read performance for large sequential reads.
gluster volume set $VOLUME_NAME performance.read-ahead on

# Enable write-behind to optimize write performance.
gluster volume set $VOLUME_NAME performance.write-behind on

# Enable quick-read for faster small file reads.
gluster volume set $VOLUME_NAME performance.quick-read on

# Enable open-behind to allow the application to open files in parallel.
gluster volume set $VOLUME_NAME performance.open-behind on

# Enable stat-prefetch for faster stat operations.
gluster volume set $VOLUME_NAME performance.stat-prefetch on

# Set the read-ahead page count for sequential reads.
gluster volume set $VOLUME_NAME performance.read-ahead-page-count 16

# Increase the write-behind window size to optimize large write operations.
gluster volume set $VOLUME_NAME performance.write-behind-window-size 4MB

# Enable eager-lock for faster file locking.
gluster volume set $VOLUME_NAME cluster.eager-lock on

# Enable parallel readdir to improve performance when listing directories with many files.
gluster volume set $VOLUME_NAME performance.parallel-readdir on

# Set the IO thread count to a higher value for better concurrency.
gluster volume set $VOLUME_NAME performance.io-thread-count 64

# Enable flush-behind to improve the latency of sequential write operations.
gluster volume set $VOLUME_NAME performance.flush-behind on

# Optimize network compression
gluster volume set $VOLUME_NAME network.compression off

# Enable RDMA for higher throughput between nodes
gluster volume set $VOLUME_NAME transport.rdma on

# Enable strict write-ordering to avoid data inconsistency during parallel writes
gluster volume set $VOLUME_NAME performance.strict-write-ordering on

# Set high-priority threads for background operations (like self-heal)
gluster volume set $VOLUME_NAME performance.high-prio-threads 32

# Apply changes to rebalance settings to improve distribution performance
gluster volume set $VOLUME_NAME cluster.rebalance-throttle aggressive

# Enable RDMA transport for better network performance between Gluster nodes
gluster volume set $VOLUME_NAME transport.rdma on

# Optionally, if you are using Gluster volumes across multiple sites with replication, ensure replication optimizations
gluster volume set $VOLUME_NAME cluster.self-heal-window-size 512
gluster volume set $VOLUME_NAME cluster.data-self-heal-algorithm full

echo "Gluster volume performance settings updated!"
