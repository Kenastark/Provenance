import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useRole } from "../../lib/role";
import { SignInScreen } from "./SignInScreen";

/**
 * Renders the sign-in screen instead of `children` until a role has been chosen
 * in this browser (`useRole().signedIn`, backed by `provenance.role` in
 * localStorage - see lib/role.tsx). Once signed in, `children` - the dashboard
 * shell - renders exactly as it did before this screen existed.
 */
export function SignInGate({ children }: { children: ReactNode }) {
  const { role, canSwitch, signedIn, signIn } = useRole();
  const wasSignedIn = useRef(signedIn);

  useEffect(() => {
    // Only the transition into the dashboard moves focus - not the initial
    // render of an already-signed-in browser, which should behave exactly like
    // today: focus starts at the top of the document, same as before this gate.
    if (!wasSignedIn.current && signedIn) {
      document.getElementById("main")?.focus();
    }
    wasSignedIn.current = signedIn;
  }, [signedIn]);

  if (!signedIn) {
    return <SignInScreen role={role} canSwitch={canSwitch} onSelectRole={signIn} />;
  }

  return <>{children}</>;
}
