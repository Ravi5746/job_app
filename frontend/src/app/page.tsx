import { redirect } from 'next/navigation';

export default function Home() {
  // Simple redirect to login or dashboard
  // Middleware will handle the logic if session exists
  redirect('/login');
}
