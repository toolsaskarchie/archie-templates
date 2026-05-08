# Archie Instance Bootstrap

CloudFormation template + scripts customers run **once** in their AWS account before deploying an Archie instance from app.askarchie.io.

## What it does

`archie-instance-bootstrap.cfn.yaml` creates two things in your account:

1. **`ArchieDeployerRole`** — a cross-account IAM role the Archie SaaS worker assumes to deploy CloudFormation stacks into your account. Trusted via a shared external ID (you supply on stack creation).
2. **Seven SSM SecureString parameters** with the OAuth + NextAuth secrets your Archie instance reads at deploy time.

After this stack creates, you send the `DeployerRoleArn` + `ExternalId` to your Archie deployer (over a secure channel — 1Password, encrypted email). They paste both into the **Admin · Archie Self** deploy form on app.askarchie.io. ~22 minutes later your Archie instance is live.

## Prerequisites — gather before running

- **GitHub PAT** — fine-grained, scope `Contents: read+write` on `toolsaskarchie/archie-templates`
- **GitHub OAuth app** — github.com → Settings → Developer settings → OAuth Apps → New OAuth App. Authorization callback: `https://<your-archie-domain>/api/auth/callback/github`. Copy the client secret.
- **Google OAuth client** — console.cloud.google.com → APIs & Services → Credentials. Authorized redirect URI: `https://<your-archie-domain>/api/auth/callback/google`. Copy the client secret.
- **NextAuth secret** — generate locally: `openssl rand -base64 44`
- **External ID** — random shared secret: `openssl rand -hex 16`. You'll send this to your Archie deployer.
- **(Optional) Azure AD app** — only if you want Microsoft sign-in. Otherwise leave the three Azure AD parameters at their defaults.
- **ACM certificate** in `us-east-1` for your chosen domain — must already exist (CloudFront requirement). DNS-validated.
- **Bedrock model access** in your account: request access to Claude Sonnet 4 + Claude Haiku 3.5 (or 4.5) at console.aws.amazon.com → Bedrock → Model access. Required for Studio AI features.

## Run it

### Option A — AWS Console

1. Sign in to your AWS account, go to **CloudFormation** → **Create stack** → **With new resources**
2. Upload the `archie-instance-bootstrap.cfn.yaml` template
3. Stack name: `archie-instance-bootstrap`
4. Fill in the parameters (most are NoEcho — values won't be printed in CloudFormation events)
5. Acknowledge the IAM capability prompt (`CAPABILITY_NAMED_IAM`)
6. **Create stack** — takes ~30 seconds

### Option B — AWS CLI

```bash
aws cloudformation create-stack \
  --stack-name archie-instance-bootstrap \
  --template-body file://archie-instance-bootstrap.cfn.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters \
      ParameterKey=ExternalId,ParameterValue=<random-hex-string> \
      ParameterKey=GithubToken,ParameterValue=<your-pat> \
      ParameterKey=GithubOAuthSecret,ParameterValue=<github-oauth-secret> \
      ParameterKey=GoogleOAuthSecret,ParameterValue=<google-oauth-secret> \
      ParameterKey=NextAuthSecret,ParameterValue=<random-base64-44>
```

After the stack creates, get the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name archie-instance-bootstrap \
  --query 'Stacks[0].Outputs' \
  --output table
```

Send `DeployerRoleArn` + `ExternalId` to your Archie deployer.

## Re-running / updating

The template is idempotent on update — re-run with new parameter values to rotate any secret. CloudFormation only changes the SSM parameters whose values changed.

## Tear-down

If you decide to remove your Archie instance:

1. First destroy the Archie instance via the Admin · Archie Self UI (it'll un-deploy the Backend, Frontend, and Templates Seed CFN stacks)
2. Then delete this bootstrap stack — removes the SSM params and the IAM role

Don't reverse the order — the deployer role is needed to clean up the Archie stacks.

## Security notes

- `ArchieDeployerRole` carries `AdministratorAccess` because deploys provision arbitrary AWS resources (RDS, EC2, Lambda, etc). If your org has a tighter posture, scope down via SCPs in your AWS Organizations master account. We're working on a permission-boundary version for enterprise pilots.
- `ExternalId` is the only thing standing between your account and a malicious AssumeRole call. Treat it like a password. Rotate by updating this stack with a new value and notifying your deployer.
- All seven SSM parameters are `String` (not `SecureString`) because CloudFormation's `{{resolve:ssm-secure:...}}` reference doesn't compose with Lambda environment variables. The parameters are still encrypted-at-rest by AWS-managed KMS keys; the trade-off is that Lambda env vars hold plaintext at runtime. Deployer role policy can restrict who reads SSM `/archie/*` if you want to lock that down further.
