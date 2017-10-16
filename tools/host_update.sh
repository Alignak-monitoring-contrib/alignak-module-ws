#!/usr/bin/env bash
curl -vX PATCH -H "Content-Type: application/json" --user "1506075585665-fa588bf3-3587-4553-8e19-c47c3ab90768" -d @$1 "http://demo.alignak.net:8888/host"
