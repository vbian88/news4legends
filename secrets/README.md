# Local secrets

Create `llm_api_key` here during installation. It is mounted read-only and ignored by Git.

```bash
printf '%s' 'PASTE_YOUR_LLM_API_KEY_HERE' > secrets/llm_api_key
chmod 600 secrets/llm_api_key
```

Never commit real keys, tokens, private keys, or backups.
