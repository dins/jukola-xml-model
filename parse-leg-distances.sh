#!/usr/bin/env bash

# ./parse-leg-distances.sh 2009 ve
# time for year in $(seq 1992 2019); do ./parse-leg-distances.sh $year ve; done

YEAR=$1
VE_OR_JU=$2
DISTANCES=$(curl -s https://results.jukola.com/tulokset/fi/j${YEAR}_${VE_OR_JU}/ | grep "/tulokset/fi/j${YEAR}_${VE_OR_JU}/${VE_OR_JU}/tilanne/" | grep -E "Vaihto |Maali " | cut -d " " -f 3| tr , . | tr '\n' ', ')
DISTANCES=$(echo "$DISTANCES"| sed 's/\(.*\),/\1 /')
echo "$YEAR: [$DISTANCES],"