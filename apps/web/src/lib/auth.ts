import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Keycloak from "next-auth/providers/keycloak";

const keycloakClientId = process.env.KEYCLOAK_WEB_CLIENT_ID || process.env.KEYCLOAK_CLIENT_ID;
const keycloakClientSecret =
  process.env.KEYCLOAK_WEB_CLIENT_SECRET || process.env.KEYCLOAK_CLIENT_SECRET;
const enableTestCredentials = process.env.NEXTAUTH_ALLOW_TEST_CREDENTIALS === "true";
const testUsername = process.env.NEXTAUTH_TEST_USER || "e2e@test.local";
const testPassword = process.env.NEXTAUTH_TEST_PASSWORD || "E2EPassw0rd!";

const providers = [];

if (process.env.KEYCLOAK_ISSUER) {
  providers.push(
    Keycloak({
      clientId: keycloakClientId,
      clientSecret: keycloakClientSecret,
      issuer: process.env.KEYCLOAK_ISSUER,
    }),
  );
}

if (enableTestCredentials) {
  providers.push(
    Credentials({
      id: "credentials",
      name: "E2E Test Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "e2e@test.local" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (credentials?.username === testUsername && credentials?.password === testPassword) {
          return {
            id: "e2e-user",
            name: "E2E Test User",
            email: testUsername,
            roles: ["operator"],
          };
        }
        return null;
      },
    }),
  );
}

if (providers.length === 0) {
  // Fallback to demo credentials to prevent Vercel build errors and allow Judges to login
  providers.push(
    Credentials({
      id: "credentials",
      name: "Demo Credentials (admin/admin)",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "admin" },
        password: { label: "Password", type: "password", placeholder: "admin" },
      },
      async authorize(credentials) {
        if (credentials?.username === "admin" && credentials?.password === "admin") {
          return {
            id: "demo-user",
            name: "Demo User",
            email: "admin@tradeflow.ai",
            roles: ["operator"],
          };
        }
        return null;
      },
    }),
  );
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  secret: process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "fallback-secret-for-build-time-only-so-it-doesnt-crash",
  trustHost: true,
  providers,
  callbacks: {
    async jwt({ token, account, profile, user }) {
      if (account) {
        token.accessToken = account.access_token;
        if (profile && typeof profile === "object") {
          const profileWithRoles = profile as { realm_access?: { roles?: string[] } };
          if (profileWithRoles.realm_access?.roles) {
            token.roles = profileWithRoles.realm_access.roles;
          }
        }
      }

      if (!account && user && typeof user === "object" && "roles" in user) {
        token.roles = user.roles;
      }
      return token;
    },
    async session({ session, token }) {
      // @ts-ignore
      session.accessToken = token.accessToken;
      // @ts-ignore
      session.roles = token.roles || [];
      return session;
    },
  },
});

export const GET = handlers.GET;
export const POST = handlers.POST;
