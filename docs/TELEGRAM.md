# Telegram delivery

Telegram receives the compact `telegram` field from the same delivery bundle used for email. It does not trigger another collection or LLM pass.

## 1. Create a bot

In Telegram, open the verified **BotFather** account, start it, send `/newbot`, choose a display name and unique username, and copy the token. Treat the token as a password. Never put it in this repository, `.env.example`, screenshots, issues, or workflow exports.

## 2. Prepare the destination

For a private chat, start a conversation with the bot and send a message. For a group/channel, add the bot and grant only the permission required to post. Channels may require administrator posting rights.

Obtain the destination/chat ID using a trusted method such as Telegram's Bot API `getUpdates` after sending the bot a test message, or n8n's supported destination selector if available. Group/channel IDs can be negative. Verify the ID belongs to the intended destination; do not publish it.

## 3. Create the n8n credential

In n8n, open **Credentials**, create a Telegram API credential, paste the bot token, save, and test if the UI offers a connection test. The token is stored in n8n persistent state; protect and back up `n8n_data`.

## 4. Configure the node

Open **Send a text message** in the imported workflow:

- Credential: your Telegram bot credential
- Chat ID: your verified private/group/channel ID
- Text: `{{ $json.telegram }}`
- Keep parse mode disabled unless you have verified renderer compatibility

Enable the node only after these fields are correct.

## 5. Test

**What you're doing:** Sending a real compact digest to the intended destination.

**Action — n8n UI:** Execute the HTTP node, inspect that `telegram` is non-empty, then execute the Telegram node.

**What you should see:** One message in the intended chat containing profile headings and compact stories.

**If you don't see it:** Check the node execution error, credential, chat ID, whether the user started the bot, and group/channel permissions.

**Don't continue until a manual message arrives in the correct destination.**

Then execute the entire workflow and **Publish** it before relying on the schedule.

## Message size

The orchestrator applies an approximately 4,000-character global fair-share budget across enabled profile digests. This stays near Telegram's message limit while leaving headroom. Content may be truncated with an ellipsis; use email for richer coverage. If Telegram still rejects a message, inspect actual length and unexpected formatting rather than raising the LLM limit.

## Enable or disable delivery

Disabling the Telegram n8n node stops Telegram delivery. The worker may still render the field; local rendering is inexpensive and does not invoke another LLM. Re-enable the node, test, and Publish to resume scheduled delivery.

## Troubleshooting

| Symptom | Fastest check | Likely fix |
| --- | --- | --- |
| Unauthorized | Test credential | Replace/revoke compromised or mistyped token |
| Chat not found | Recheck destination ID | Start bot; use correct negative group/channel ID |
| Forbidden | Inspect membership/permissions | Add bot or grant posting permission |
| Empty text | Inspect HTTP node `telegram` | Fix profile/article pipeline first |
| Message too long | Count output characters | Review renderer/version; do not duplicate messages blindly |
| Manual works, schedule does not | Check active Published version | Publish the tested workflow |

Never paste tokens or full execution data into a public issue.

