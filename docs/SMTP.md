# SMTP email delivery

News 4 Legends renders one HTML email from the same collection and LLM synthesis pass used for the optional Telegram digest. n8n sends that HTML through a standard SMTP account; Gmail OAuth is not required.

## What you need

- SMTP hostname, port and encryption mode from your mail provider
- SMTP username and password or provider-issued App Password
- permitted From address
- destination To address and optional BCC recipients

Use placeholders in notes and screenshots. Never commit SMTP credentials or personal recipient addresses.

## Create the n8n SMTP credential

In n8n, open **Credentials**, create an **SMTP** credential, and enter the values supplied by your provider:

| Setting | Example placeholder |
| --- | --- |
| Host | `<SMTP_HOST>` |
| Port | `587` for STARTTLS or the provider's documented port |
| User | `<SMTP_USER>` |
| Password | `<SMTP_PASSWORD>` |
| SSL/TLS | Match the provider's documented mode |

Prefer a dedicated account or App Password when the provider supports one. Do not place the password in the workflow JSON, `.env.example`, documentation or Git history.

## Configure the email node

Import `n8n/workflow.example.json`, open **Send an Email**, and configure:

- Credential: the SMTP credential created above
- From: a sender allowed by the SMTP account
- To: your chosen recipient
- BCC: optional private recipients
- Subject: `News 4 Legends — Daily Intelligence Digest`
- Email format: HTML
- HTML body: `{{ $json.email }}`

The public example is disabled and contains placeholders. Enable it only after replacing every placeholder and successfully testing delivery.

## Test before scheduling

1. Execute the HTTP Request node and confirm it returns a non-empty `email` field.
2. Execute **Send an Email** with a controlled recipient.
3. Confirm the message arrives and renders as HTML.
4. Check the n8n execution result for SMTP errors.
5. Publish the workflow after the test succeeds.

Saving an editor change is not enough when the live workflow is still on an older published version. Publish it, and restart n8n only if the installed n8n version requires that for imported or published changes to take effect.

## Troubleshooting

- **Authentication failed:** verify username, password/App Password and provider security requirements.
- **Connection refused or timed out:** verify hostname, port, firewall and TLS/SSL mode.
- **Sender rejected:** use a From address authorized for the SMTP account.
- **Message is plain text:** set the node to HTML and use `{{ $json.email }}` in the HTML field.
- **Message missing:** inspect the n8n execution, spam filtering, recipient address and provider sending limits.
- **Multiple private recipients:** use BCC so recipients do not see one another's addresses.

SMTP credentials are stored in n8n's persistent encrypted credential state. Protect and back up the complete `n8n_data` volume and its encryption state.
