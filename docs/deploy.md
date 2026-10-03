# Deploying Researchly: the owner's guide

This guide covers the steps only the owner can do: creating accounts and
clicking "approve". Everything else is automated. Allow about 40 minutes the
first time. **No step asks you to copy a password, key or token into chat or
into the repository.**

The steps produce:

| Piece | Where | Cost at student scale |
|---|---|---|
| Engine: analysis plus the LanguageTool sidecar | Google Cloud Run, Singapore | ~$0 (scales to zero, free tier); ~$10–15/month if kept warm in term time |
| Website | Vercel Hobby, Singapore | $0. Allowed because Researchly is free and non-commercial (D2) |

## 0. Merge the pull request first (2 minutes)

Vercel and the deploy workflow both read `main`, and until the pull request
is merged, `main` still has the old prototype layout: no `apps/web`, no
`services/engine`, no bootstrap script.

1. Open the pull request (amriitmohapatra/Researchly#1) and check that every
   CI check is green.
2. Click **Merge pull request** and choose **Create a merge commit**, which
   keeps each commit's evidence in history. Then **Confirm merge**.

> **Don't see `apps/web` in Vercel's Root Directory picker?** The pull
> request isn't merged yet: the picker lists folders on `main`. Merge it,
> then cancel the import and start **Add New… → Project** again so Vercel
> re-reads the repository.

---

## 1. Google Cloud project (about 15 minutes)

1. Go to <https://console.cloud.google.com> and sign in.
2. Create a project. Call it, for example, `researchly-prod` and note its
   **project ID** (shown under the name; it may have a number suffix).
3. Turn on **billing** for the project. Cloud Run needs a billing account
   even inside the free tier.
4. Set a budget alert: **Billing → Budgets & alerts → Create budget**, for
   example USD 10/month with email alerts at 50%, 90% and 100%. The engine
   is capped at 2 instances, so the alert is a backstop, not an expectation.

## 2. Run the bootstrap script in Cloud Shell (about 5 minutes)

1. In the console, click the **`>_` (Activate Cloud Shell)** button at the
   top right. A terminal opens in the browser, already signed in.
2. On GitHub, open `services/engine/deploy/bootstrap-gcp.sh` on `main`
   and click **Copy raw file**.
3. In Cloud Shell, type `nano bootstrap-gcp.sh`, paste, then press
   `Ctrl+O`, `Enter`, `Ctrl+X`.
4. Run it, using your project ID:

   ```bash
   bash bootstrap-gcp.sh YOUR_PROJECT_ID
   ```

   It is safe to run twice. It creates:
   - an image registry;
   - two service accounts: the engine's own, with **no** permissions, and a
     deployer;
   - a trust link that lets *only* `amriitmohapatra/Researchly`'s GitHub
     Actions deploy, using short-lived tokens. No key files are involved.
5. At the end it prints three lines: `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`,
   `GCP_DEPLOY_SA`. These are identifiers, not secrets. Keep the window open.

## 3. Tell GitHub where to deploy (about 3 minutes)

1. Open <https://github.com/amriitmohapatra/Researchly/settings/variables/actions>.
2. Under **Variables** (not Secrets), click **New repository variable** three
   times, once for each value the script printed.
3. Open **Settings → Environments → New environment** and create one named
   `production`. Optionally, under **Required reviewers**, add yourself, so
   every deploy waits for your click.

## 4. Create the website on Vercel (about 10 minutes)

1. Go to <https://vercel.com/signup> and sign up **with GitHub**, on the
   Hobby plan.
2. Click **Add New… → Project**, then import `amriitmohapatra/Researchly`.
   Grant Vercel access to that repository only.
3. Before deploying, set:
   - **Root Directory:** `apps/web`. The picker is a folder tree: click the
     arrow next to `apps` (not its radio button) and select `web`. Leave
     "Include files outside the Root Directory" **on**, because the web app
     reads the API contract from `packages/contract`.
   - **Environment variable:** `NEXT_PUBLIC_ENGINE_URL` =
     `https://placeholder.invalid`, with type **Config** (not Secret). You'll
     replace the value in step 6.

   > **Picker doesn't offer `apps/web`?** Leave Root Directory as `./` and
   > deploy anyway. That first build fails, which is expected. Then go to
   > **Settings → Build and Deployment** (or **General**), type `apps/web` into
   > **Root Directory**, keep "Include files outside the root directory" on,
   > click **Save**, and **Redeploy**. (Worked for the owner, 2026-10-03.)

   > **Why Config, not Secret?** A `NEXT_PUBLIC_` value is built into the page
   > the browser downloads, so it can't be secret, and Vercel warns if you
   > try. The engine address isn't a secret anyway: the browser has to know
   > it to send text there. Vercel can't convert a Secret into a Config. If
   > you saved it as Secret, **delete it and add it again** as Config. If
   > Config is greyed out, turn off **Team Settings → Security & Privacy →
   > "Enforce Sensitive Environment Variables"** first.
4. Click **Deploy**. When it finishes, note the production address, for
   example `https://researchly-xyz.vercel.app`.
5. **Settings → Deployment Protection:** keep **Vercel Authentication** on
   (Standard Protection). On Hobby this protects preview links but not the
   production address. Until accounts arrive in S2, the production site is
   unlisted, not private.

## 5. Deploy the engine (about 5 minutes)

1. Open <https://github.com/amriitmohapatra/Researchly/actions/workflows/deploy-engine.yml>.
2. Click **Run workflow** and choose branch `main`.
3. In **allowed_origins**, enter the Vercel production address from step
   4.4, for example `https://researchly-xyz.vercel.app`. It must be https,
   with no trailing slash or path.
4. If you added yourself as a reviewer, approve the run.
5. When it turns green, open the run's **Summary**. It shows the engine
   URL, for example `https://researchly-engine-abc-as.a.run.app`, and the
   health of every tier.

## 6. Connect the two (about 3 minutes)

1. In Vercel, go to **Settings → Environment Variables** and set
   `NEXT_PUBLIC_ENGINE_URL` to the engine URL from step 5.5, with type
   **Config**, for Production and Preview, and no trailing slash. If the old
   placeholder was saved as Secret, delete it and add it again (see the note
   in step 4.3).
2. Go to **Deployments**, open the latest one, choose **⋯ → Redeploy**. The
   engine address is built into the page and its security policy, so a
   redeploy is needed.

## 7. Check it works (2 minutes)

1. Open your Vercel address, click **Insert an example draft**, then
   **Check**.
2. You should see suggestions, highlights and no warning banner. The first
   check after a quiet period can take about 10 seconds while the engine
   wakes up; later ones take well under a second.
3. Tell me the two addresses (website and engine). I'll run the latency
   measurements against the real deployment and tick the S1 boxes in
   `PLAN.md`.

---

## Later deploys

- **Website:** automatic. Every push to `main` deploys production, and every
  pull request gets a protected preview.
- **Engine:** run **Deploy engine** again (step 5) whenever you want to
  release what's on `main`.
- **Previews can't reach the production engine.** The engine accepts
  browsers only from the origins you listed, and preview addresses change
  with every deploy. This is deliberate in S1: previews are checked with
  the mocked engine in CI.

## Changing your mind

| Want to… | Do this |
|---|---|
| Avoid cold starts in term time | In `services/engine/deploy/cloudrun.service.yaml` set `minScale: "1"`, then redeploy the engine (~$10–15/month) |
| Stop everything | Cloud Run → `researchly-engine` → Delete; Vercel → Project → Settings → Delete |
| Move to a custom domain | Add it in Vercel → Domains, then redeploy the engine with the new origin in `allowed_origins` |
