export MERMAID_FILTER_WIDTH=2000;
for f in ./*.md; do
    pandoc -F mermaid-filter -o "./pdf/${f%.md}.pdf" "$f"
done
