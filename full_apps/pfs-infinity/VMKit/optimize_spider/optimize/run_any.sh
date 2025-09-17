#!/bin/bash

pproxy --reuse -l 'socks5://10.1.1.111:8888' -ur "socks5://10.1.1.111:8888" -r "http" -v -d --sys --ssl registry.hg.local.crt 
