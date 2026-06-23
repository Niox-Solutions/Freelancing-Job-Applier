from dataclasses import dataclass
from typing import Callable

from selenium.common.exceptions import TimeoutException, WebDriverException

from login_flows import run_google_login_case, run_nafezly_email_login_case


@dataclass
class LoginCase:
    name: str
    description: str
    run: Callable[[], None]


def run_case(case: LoginCase) -> dict:
    print(f"\n{'=' * 60}")
    print(f"CASE: {case.name}")
    print(f"      {case.description}")
    print("=" * 60)

    try:
        case.run()
        print("RESULT: SUCCESS")
        return {"name": case.name, "status": "SUCCESS", "error": None}
    except (TimeoutException, WebDriverException, OSError, RuntimeError) as exc:
        print(f"RESULT: FAILED - {exc}")
        return {"name": case.name, "status": "FAILED", "error": str(exc)}
    except Exception as exc:
        print(f"RESULT: ERROR - {exc}")
        return {"name": case.name, "status": "ERROR", "error": str(exc)}


def google_case(
    name: str,
    description: str,
    *,
    use_profile: bool = False,
    via_homepage: bool = True,
    wait_for_popup: bool = True,
    fill_email: bool = True,
    fill_password: bool = True,
) -> LoginCase:
    return LoginCase(
        name=name,
        description=description,
        run=lambda: run_google_login_case(
            use_profile=use_profile,
            via_homepage=via_homepage,
            wait_for_popup=wait_for_popup,
            fill_email=fill_email,
            fill_password=fill_password,
        ),
    )


def nafezly_case(name: str, description: str, *, via_homepage: bool) -> LoginCase:
    return LoginCase(
        name=name,
        description=description,
        run=lambda: run_nafezly_email_login_case(via_homepage=via_homepage),
    )


def run_cases_until_success(cases: list[LoginCase]) -> list[dict]:
    results = []

    for case in cases:
        result = run_case(case)
        results.append(result)

        if result["status"] == "SUCCESS":
            print(f"\nSigned in with: {case.name}")
            print("Stopping because sign in succeeded.")
            break

        print("Trying next sign-in approach...")

    return results


CASES = [
    google_case(
        name="your_approach_homepage_email_password",
        description="Fresh Chrome, homepage -> login, Google, email -> try again -> email + password + sign in",
        wait_for_popup=False,
    ),
    google_case(
        name="your_approach_with_popup_wait",
        description="Fresh Chrome, homepage -> login, Google, wait for popup, email + password",
    ),
    google_case(
        name="direct_login_full_credentials",
        description="Fresh Chrome, open /login directly, Google, wait for popup, email + password",
        via_homepage=False,
    ),
    google_case(
        name="profile_approach_homepage",
        description="Chrome profile, homepage -> login, Google, rely on saved Google session",
        use_profile=True,
        fill_email=False,
        fill_password=False,
    ),
    google_case(
        name="profile_approach_direct_login",
        description="Chrome profile, open /login directly, Google, rely on saved Google session",
        use_profile=True,
        via_homepage=False,
        fill_email=False,
        fill_password=False,
    ),
    nafezly_case(
        name="nafezly_email_password_direct",
        description="Fresh Chrome, /login directly, site email + password (not Google OAuth)",
        via_homepage=False,
    ),
    nafezly_case(
        name="nafezly_email_password_homepage",
        description="Fresh Chrome, homepage -> login, site email + password (not Google OAuth)",
        via_homepage=True,
    ),
]
