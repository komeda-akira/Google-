# Google Calendar（iCal）の変化を検知し、変更があれば LINE に通知する
# スケジュール: UTC 0:00 = 日本時間 9:00（JST）
# 必要な Secrets: ICAL_URL, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID

name: Calendar change notify to LINE

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: calendar-line-notify
  cancel-in-progress: false

jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Check calendar and notify LINE
        env:
          ICAL_URL: ${{ secrets.ICAL_URL }}
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
        run: python scripts/notify_calendar.py

      - name: Commit snapshot hash if updated
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data/last_ical_sha256.txt
          if git diff --staged --quiet; then
            echo "No hash file change to commit."
          else
            git commit -m "chore: update calendar iCal snapshot hash"
            git push
          fi
