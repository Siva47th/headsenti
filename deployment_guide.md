# 100% Free Cloud Deployment Guide (No Credit Card Required)

This guide walks you through deploying your News Sentiment & Trend Pipeline to the cloud for **$0/month** without ever entering a credit card.

We will use:
1. **Neon.tech** to host the PostgreSQL database.
2. **GitHub Actions** to run the scraper, transform, and load pipeline every 6 hours.
3. **Vercel** to host the FastAPI backend and HTML dashboard.

---

## Step 1: Set up your Free PostgreSQL Database on Neon.tech

1. Visit [Neon.tech](https://neon.tech/) and click **Sign Up** (use Google or GitHub to sign up without a credit card).
2. Create your project `headsenti` (choose **Singapore** region and Postgres version 18). Keep **Neon Auth** toggled **OFF**.
3. Copy your connection details from the popup. They will look like this:
   `postgresql://neondb_owner:npg_9pxljtagqLe3@ep-morning-fog-azz2bod4.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`

---

## Step 2: Set up GitHub Actions for Scrapers (Free Scheduler)

GitHub Actions will run your Python scraper scripts on a timer (cron schedule) every 6 hours.

1. Create a free account on [GitHub](https://github.com/) (no card required).
2. Create a new repository (e.g. `news-sentiment-pipeline`) and set it to **Private** or **Public**.
3. Push your codebase to this GitHub repository.
4. Add your database credentials as GitHub **Secrets**:
   - Go to your repository on GitHub ➔ **Settings** ➔ **Secrets and variables** ➔ **Actions**.
   - Click **New repository secret** for each of these 5 variables:
     - Name: `DB_USER` ➔ Value: `neondb_owner`
     - Name: `DB_PASSWORD` ➔ Value: `npg_9pxljtagqLe3`
     - Name: `DB_HOST` ➔ Value: `ep-morning-fog-azz2bod4.c-3.ap-southeast-1.aws.neon.tech`
     - Name: `DB_PORT` ➔ Value: `5432`
     - Name: `DB_NAME` ➔ Value: `neondb`
5. Once pushed, the workflow `.github/workflows/scrape.yml` will automatically run every 6 hours and update your Neon database!
   - You can also run it manually: Go to the **Actions** tab on GitHub, click **News Scraper Pipeline** in the sidebar, and click **Run workflow**.

---

## Step 3: Deploy the Dashboard to Vercel (Free Serverless Hosting)

Vercel will build your FastAPI backend and HTML frontend and serve them at a public URL.

1. Go to [Vercel](https://vercel.com/) and sign up for a **Hobby** account (use your GitHub account to sign up instantly without a credit card).
2. Click **Add New** ➔ **Project**.
3. Select your GitHub repository (`news-sentiment-pipeline`) and click **Import**.
4. In the **Environment Variables** dropdown on Vercel, add the database variables:
   - `DB_USER` ➔ `neondb_owner`
   - `DB_PASSWORD` ➔ `npg_9pxljtagqLe3`
   - `DB_HOST` ➔ `ep-morning-fog-azz2bod4.c-3.ap-southeast-1.aws.neon.tech`
   - `DB_PORT` ➔ `5432`
   - `DB_NAME` ➔ `neondb`
5. Click **Deploy**.
6. Once deployed, Vercel will give you a public URL (e.g. `https://your-project-name.vercel.app`) to view your gorgeous dark glassmorphism dashboard from anywhere!
