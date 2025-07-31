#!/bin/bash
OUTPUT=$(eval "$1" 2>&1)
echo "$OUTPUT" > /app/terminal_output.txt
echo "Output saved to /app/terminal_output.txt"
