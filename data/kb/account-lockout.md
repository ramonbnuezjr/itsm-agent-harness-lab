# Account Lockout and Password Reset

Use this runbook for failed sign-in attempts, locked accounts, or forgotten passwords.

1. Verify the requester's identity using the approved service-desk verification process.
2. Check whether the account is locked, disabled, or affected by a wider identity-provider incident.
3. Direct verified users to the approved self-service password reset flow.
4. Never ask a user to disclose an existing or newly created password.
5. Escalate disabled privileged accounts and repeated lockouts to identity operations.

Document the verification method, account state, and escalation target without placing secrets in the incident record.
