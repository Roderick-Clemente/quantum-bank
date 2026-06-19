import re

import pytest


def _enable_rollout(monkeypatch, schema: str, feature: str, force: str):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", schema)
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", feature)
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", force)

    import models

    models.init_db()


def _login_demo(client):
    response = client.post("/login", data={"username": "demo"}, follow_redirects=True)
    assert response.status_code == 200


def _get_checking_to_savings_accounts(client):
    accounts = client.get("/api/accounts").get_json()["accounts"]
    checking = next(a for a in accounts if a["account_type"] == "checking")
    savings = next(a for a in accounts if a["account_type"] == "savings")
    return checking, savings


def _post_transfer(client, amount):
    checking, savings = _get_checking_to_savings_accounts(client)
    return client.post(
        "/transfer",
        data={
            "from_account": str(checking["id"]),
            "to_account": str(savings["id"]),
            "amount": str(amount),
            "description": "rewards rollout test",
        },
        follow_redirects=True,
    )


def _get_dashboard(client):
    return client.get("/dashboard", follow_redirects=True)


def _extract_rewards_points(response):
    match = re.search(rb'data-testid="rewards-points">\s*(\d+)\s*<', response.data)
    if not match:
        return None
    return int(match.group(1))


@pytest.mark.banking
def test_transfer_succeeds_when_rewards_flags_are_all_off(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "off")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "off")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "off")
    _login_demo(client)

    response = _post_transfer(client, 10.0)

    assert response.status_code == 200
    assert b"Transfer successful" in response.data


@pytest.mark.banking
def test_dashboard_hides_rewards_when_rollout_flags_are_all_off(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "off")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "off")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "off")
    _login_demo(client)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points"' not in response.data
    assert b'data-testid="rewards-banner"' not in response.data


@pytest.mark.banking
def test_dashboard_shows_legacy_banner_when_feature_is_enabled_before_schema(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "off")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "on")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "off")
    _login_demo(client)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points"' not in response.data
    assert b'data-testid="rewards-banner"' in response.data
    assert b'data-kind="legacy_no_schema"' in response.data


@pytest.mark.banking
def test_dashboard_shows_no_rewards_state_when_schema_ready_but_feature_off(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "on")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "off")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "off")
    _login_demo(client)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points"' not in response.data
    assert b'data-testid="rewards-banner"' not in response.data


@pytest.mark.banking
def test_dashboard_shows_rewards_points_when_schema_and_feature_are_enabled(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    _enable_rollout(monkeypatch, schema="on", feature="on", force="off")
    _login_demo(client)
    _post_transfer(client, 10.0)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-banner"' not in response.data
    assert re.search(rb'data-testid="rewards-points">\s*\d+\s*<', response.data)


@pytest.mark.banking
def test_dashboard_shows_forced_fail_banner_when_migration_failure_is_forced(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "on")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "on")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "on")
    _login_demo(client)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points"' not in response.data
    assert b'data-testid="rewards-banner"' in response.data
    assert b'data-kind="rollback_forced_fail"' in response.data


@pytest.mark.banking
def test_transfer_under_forced_failure_still_returns_success(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "on")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "on")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "on")
    _login_demo(client)

    response = _post_transfer(client, 10.0)

    assert response.status_code == 200
    assert b"Transfer successful" in response.data


@pytest.mark.banking
def test_forced_fail_transfer_writes_no_visible_points_row(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "on")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "on")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "on")
    _login_demo(client)
    _post_transfer(client, 10.0)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points"' not in response.data
    assert b'data-testid="rewards-banner"' in response.data
    assert b'data-kind="rollback_forced_fail"' in response.data


@pytest.mark.banking
def test_dashboard_shows_exactly_one_point_for_ten_dollar_transfer(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    _enable_rollout(monkeypatch, schema="on", feature="on", force="off")
    _login_demo(client)
    _post_transfer(client, 10.0)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points">1<' in response.data


@pytest.mark.banking
def test_dashboard_does_not_increment_points_for_sub_ten_dollar_transfer(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    _enable_rollout(monkeypatch, schema="on", feature="on", force="off")
    _login_demo(client)
    _post_transfer(client, 5.0)
    _post_transfer(client, 20.0)

    response = _get_dashboard(client)

    assert response.status_code == 200
    assert b'data-testid="rewards-points">2<' in response.data


@pytest.mark.banking
def test_transfer_still_succeeds_when_rewards_insert_raises(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    monkeypatch.setenv("DEMO_ROLLOUT_SCHEMA", "on")
    monkeypatch.setenv("DEMO_ROLLOUT_FEATURE", "on")
    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "off")
    _login_demo(client)

    import models

    def _raise_rewards_insert(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(models, "try_insert_rewards_points", _raise_rewards_insert)

    response = _post_transfer(client, 10.0)

    assert response.status_code == 200
    assert b"Transfer successful" in response.data


@pytest.mark.banking
def test_rewards_total_recovers_after_forced_failure_is_cleared(
    client, monkeypatch, rollout_env, rewards_ledger_clean
):
    _enable_rollout(monkeypatch, schema="on", feature="on", force="off")
    _login_demo(client)
    _post_transfer(client, 10.0)

    before_rollback = _get_dashboard(client)
    before_points = _extract_rewards_points(before_rollback)
    assert before_rollback.status_code == 200
    assert before_points is not None

    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "on")
    _post_transfer(client, 10.0)

    during_rollback = _get_dashboard(client)
    assert during_rollback.status_code == 200
    assert b'data-testid="rewards-points"' not in during_rollback.data
    assert b'data-testid="rewards-banner"' in during_rollback.data
    assert b'data-kind="rollback_forced_fail"' in during_rollback.data

    monkeypatch.setenv("DEMO_FORCE_ROLLOUT_MIGRATION_FAIL", "off")
    _post_transfer(client, 10.0)

    response = _get_dashboard(client)
    after_points = _extract_rewards_points(response)

    assert response.status_code == 200
    assert after_points is not None
    assert after_points > before_points
