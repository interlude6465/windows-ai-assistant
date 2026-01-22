#!/bin/bash
# Fix flake8 issues

# Fix line 153 in direct_executor.py
sed -i '153s/.*/                                message="Infinite loop detected: '\''while True'\'' without " \\/' src/spectral/direct_executor.py
sed -i '154i\                                       "break or timeout",' src/spectral/direct_executor.py
sed -i '154d' src/spectral/direct_executor.py

