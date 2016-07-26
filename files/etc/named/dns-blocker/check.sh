
cd "$(dirname "$0")"
file_count="$(ls blacklists/*.txt | wc -l)"

printf "Total Files: %d\n" "$file_count"
printf "Total entries (w/ dupes): %d\n" "$(grep "^0\.0\.0\.0" blacklists/*txt | tr '\t' ' ' | tr '[:upper:]' '[:lower:]' | cut -d' ' -f 2 | sort | wc -l)"
printf "Total entries (deduped):  %d\n" "$(grep "^0\.0\.0\.0" blacklists/*txt | tr '\t' ' ' | tr '[:upper:]' '[:lower:]' | cut -d' ' -f 2 | sort | uniq -c | sort -rn | wc -l)"

for i in $(seq "$file_count"); do
    printf "%02dx entries: %d\n" "$i" "$(grep "^0\.0\.0\.0" blacklists/*txt | tr '\t' ' ' | cut -d' ' -f 2 | tr '[:upper:]' '[:lower:]' | sort | uniq -c | sort -rn | grep "\ $i\ " | wc -l)"
done
