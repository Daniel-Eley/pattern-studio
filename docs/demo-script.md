# 90-second demo

Record the real app after deployment with `DEMO_MODE=0`. Hide credentials, hosting dashboards, and personal data. Use `samples/contacts.csv`.

1. **0–10 seconds:** Show the app and say: “Pattern Studio finds and replaces spreadsheet text using plain language, with Django, React, and an LLM.”
2. **10–25 seconds:** Upload the sample CSV. Show its original Name and Email columns.
3. **25–45 seconds:** Enter “Find email addresses in the Email column”, enter `REDACTED`, and select Preview changes. Show the generated regex and three before/after cells.
4. **45–60 seconds:** Apply replacements. Point out that names and IDs are preserved. Download CSV and open it to verify all three emails are redacted.
5. **60–75 seconds:** Reset the dataset to show originals are preserved. Demonstrate an Excel upload or a second natural-language pattern.
6. **75–90 seconds:** Explain session isolation, regex timeouts, literal replacements, and that spreadsheet values are not sent to the LLM. Show the public URL and repository.

Upload the resulting video to GitHub and embed its attachment URL in README.md. Do not present an offline preset recording as a live LLM demonstration.
