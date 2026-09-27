# TimeBanking System

A full-stack TimeBanking application built with **Next.js 15, React 19, TypeScript, and Tailwind CSS**.

The repository is intentionally split into two applications:

- `frontend/` — user interface, running on **http://localhost:4028**
- `backend/` — API and local JSON persistence, running on **http://localhost:4029**

## Features

- User registration and login
- Member profiles and settings
- Service listings (offers and requests)
- Time-credit earning, spending, and exchange
- Member messaging
- Reviews and ratings
- Admin dashboard, analytics, members, reviews, and disputes
- Responsive Tailwind UI
- Local JSON database for development

## Requirements

- Node.js 18.18+ (Node.js 20 LTS or newer recommended)
- npm 9+

Check your versions:

```bash
node -v
npm -v
```

## Project structure

```text
Timebanking_System-main/
├── backend/
│   ├── src/app/api/       # API routes
│   ├── src/lib/           # server-side data/persistence logic
│   ├── package.json
│   └── .env.example
├── frontend/
│   ├── src/app/           # pages and UI
│   ├── src/lib/           # API client and shared state
│   ├── package.json
│   └── .env.example
└── README.md
```

## 1. Start the backend

Open Terminal 1:

```bash
cd backend
npm install
npm run dev
```

Backend:

```text
http://localhost:4029
```

The development data file is created automatically at:

```text
backend/.timebank/db.json
```

Do not commit `.timebank/` to Git.

## 2. Start the frontend

Open Terminal 2:

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:4029
```

Then start the frontend:

```bash
npm run dev
```

Frontend:

```text
http://localhost:4028
```

## 3. Test the application

Open:

```text
http://localhost:4028
```

Register a test user, sign in, and verify profile, services, credits, messages, reviews, and admin functionality as applicable.

## Useful commands

### Frontend

```bash
cd frontend
npm run dev
npm run type-check
npm run build
npm run start
```

### Backend

```bash
cd backend
npm run dev
npm run type-check
npm run build
npm run start
```

## Troubleshooting

### `Cannot reach backend`

Make sure the backend is running on port `4029` and that `frontend/.env.local` contains:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:4029
```

Restart the frontend after changing `.env.local`.

### Port already in use

The configured ports are:

- Frontend: `4028`
- Backend: `4029`

Stop the process using the port, or change the port in the corresponding `package.json` and update the frontend API URL accordingly.

### Clean reinstall

If dependencies become corrupted:

```bash
# Windows PowerShell
Remove-Item -Recurse -Force node_modules,.next -ErrorAction SilentlyContinue
npm install
```

For the backend and frontend, run the cleanup inside each directory separately.

## Important Git files

Do not commit:

```text
node_modules/
.next/
.timebank/
.env
.env.local
```

Only commit `.env.example` files containing safe development defaults.

## Development note

This project uses a file-backed JSON database for local development. It is suitable for a development/demo environment, not as a production multi-user database. For production deployment, use a proper database and configure authentication, CORS, secrets, and persistence accordingly.
