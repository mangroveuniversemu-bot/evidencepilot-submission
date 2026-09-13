# AWS runtime notes

## Credentials

Resolved through the standard AWS credential chain — SSO profile, instance
role, or environment. This repository never reads a credential from a file it
contains, and `.env.example` holds no secrets.

CI uses GitHub OIDC (`aws-actions/configure-aws-credentials@v4` with
`AWS_ROLE_ARN`), so there are no long-lived keys anywhere in the project.

## Cost posture

| Path | AWS calls |
| --- | --- |
| `make test` (94 tests) | none |
| `make demo`, `make queue`, `make collatz` | none |
| CI on push and pull request | none |
| `python -m app.main agent …` | one Bedrock conversation |
| `aws-smoke-test.yml` (manual dispatch) | one Bedrock conversation |

Live model calls run only when someone asks for them. That keeps credits for
the demo and stops a transient network failure from turning CI red for reasons
unrelated to the code.

## Region

Default `us-west-2`. Any region with the chosen Bedrock model enabled works;
pass `--region` or set `AWS_REGION`.

## Minimum IAM policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

Narrow `Resource` to the specific model ARN before anything resembling
production use.
