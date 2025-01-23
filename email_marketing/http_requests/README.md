# HTTP Tests via VS Code Extension restclient

## Install

In VS Code:
`F1` -> `ext install` -> then search for `rest-client` (https://github.com/Huachao/vscode-restclient)

## Setup Environments

In VS Code:
`F1` -> `Workspace Settings (JSON)` -> add the following option to it.

"rest-client.environmentVariables": {
    "local": {
      "endpoint_base": "http://localhost:8000",
      "login_user_email": "login@email.tld",
      "login_user_password": "local-password",
      "mail_s3_access_key_id": "access-key",
      "mail_s3_secret_key": "secret",
      "mail_s3_region": "eu-west-1",
      "mail_s3_bucket": "bucket-name",
      "mail_recipient": "configured@recipient-email.tld"
    },
    "production": {
      "endpoint_base": "https://your-host.tld",
      "login_user_email": "login@email.tld",
      "login_user_password": "prod-password"
    }
}
