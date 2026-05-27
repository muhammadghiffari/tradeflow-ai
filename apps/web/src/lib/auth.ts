import NextAuth from "next-auth"
import Keycloak from "next-auth/providers/keycloak"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET,
      issuer: process.env.KEYCLOAK_ISSUER,
    })
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account) {
        token.accessToken = account.access_token
        // Extract realm roles from profile if available
        if (profile?.realm_access?.roles) {
          token.roles = profile.realm_access.roles
        }
      }
      return token
    },
    async session({ session, token }) {
      // @ts-ignore
      session.accessToken = token.accessToken
      // @ts-ignore
      session.roles = token.roles || []
      return session
    }
  }
})
