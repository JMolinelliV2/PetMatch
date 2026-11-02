import type { Metadata } from "next";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Ingresar — MascoMatch" };

export default function LoginPage() {
  return <main id="main-content" className="page account-page">
    <h1>Ingresá a tu cuenta</h1>
    <LoginForm />
  </main>;
}
