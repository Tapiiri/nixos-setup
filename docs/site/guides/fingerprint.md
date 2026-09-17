# Fingerprint Login (Framework 16)

The `fw16` host has a Goodix fingerprint sensor (`27c6:609c`) built into the
power button. It is supported by libfprint's `goodixmoc` driver — no vendor TOD
blob is required.

## What is declarative

`hosts/fw16/configuration.nix` enables the daemon and pins the PAM surface:

```nix
services.fprintd.enable = true;
security.pam.services.sudo.fprintAuth = true;
security.pam.services.polkit-1.fprintAuth = true;
```

That covers:

| Prompt | Backed by | Behaviour |
| --- | --- | --- |
| GDM greeter | `gdm-fingerprint` PAM stack | Finger *or* password, in parallel |
| GNOME lock screen | `gdm-fingerprint` PAM stack | Finger *or* password, in parallel |
| `sudo` | `security.pam.services.sudo` | `pam_fprintd` is `sufficient`, falls back to password |
| polkit (1Password, GNOME auth dialogs) | `security.pam.services.polkit-1` | Same |

The `gdm-fingerprint` stack is created by nixpkgs automatically whenever
`services.fprintd.enable` is true — it does not need to be declared.

## What is not declarative

Fingerprint templates are biometric data captured at enrollment time, so they
cannot live in the flake. Each user enrolls once, on the machine.

This is a **match-on-chip (MOC)** sensor: templates are stored in the sensor's
own flash, *not* under `/var/lib/fprint/` — that directory does not even exist
on this host. Two consequences that matter:

- The chip has a fixed number of slots (`FP_DEVICE_ERROR_DATA_FULL` when
  exhausted). Deleting frees them for real — the daemon calls
  `fp_device_delete_print_sync`, which clears the slot in sensor flash rather
  than just forgetting fprintd's record.
- The chip enforces uniqueness across **all** slots, with no notion of users.
  See [one physical finger, one account](#one-physical-finger-one-account).

## One physical finger, one account

The goodixmoc driver runs a `duplicates-check` against everything already on the
chip. Enrolling a physical finger that is already enrolled — **even under a
different username** — fails with:

```text
Enroll result: enroll-duplicate
```

So a plan like "right middle finger for `tapiiri` *and* right middle finger for
`ilmari-offeri`" cannot work. Give each account a genuinely different physical
finger:

The assignment in use on fw16:

| Account | Finger |
| --- | --- |
| `tapiiri` | right index |
| `ilmari-offeri` | right middle |

Note the finger *name* is just a label — `right-ring-finger` is what fprintd
records, but the chip matches on the ridge pattern you actually presented.
Enrolling the wrong physical finger under a tidy-looking name is the usual way
people end up confused later.

### The finger does not choose the account

`pam_fprintd` calls `pam_get_user()`, claims the device for that one user, and
calls `VerifyStart` — it verifies, it never *identifies* across users. At GDM
you still pick the account first (click it in the user list), and only then
touch the sensor. Distinct fingers per account do not act as an account
selector; what they buy you is that each account only ever matches its own
finger.

## Enrolling

=== "GNOME Settings"

    Settings → **System** → **Users** → *your account* → **Fingerprint Login**.
    Pick a finger and follow the prompts. This is the easiest path and each user
    can do it from their own session.

=== "Command line"

    As the user being enrolled:

    ```bash
    fprintd-enroll -f right-index-finger
    ```

    Or, for another user, from a root shell:

    ```bash
    sudo -i                                              # authenticate once
    fprintd-enroll -f right-ring-finger ilmari-offeri
    ```

    Valid finger names: `{left,right}-{thumb,index,middle,ring,little}-finger`.
    Enroll a second finger per account so a bandaged or wet fingertip is not a
    lockout.

!!! warning "Use `sudo -i`, not `sudo fprintd-enroll`"

    Because `security.pam.services.sudo.fprintAuth` is on, `sudo` itself tries
    to authenticate with the sensor. It claims the device, and the
    `fprintd-enroll` it then launches cannot:

    ```text
    failed to claim device: GDBus.Error:net.reactivated.Fprint.Error.AlreadyInUse:
    Device was already claimed
    ```

    Getting a root shell first — or letting sudo's fingerprint prompt time out
    into the password fallback — avoids the collision.

## Deleting and reassigning

`fprintd-delete` takes an optional `-f` so you can drop a single finger instead
of wiping the account:

```bash
sudo -i
fprintd-delete tapiiri -f right-middle-finger   # one finger
fprintd-delete tapiiri                          # all fingers for the user
```

Reassigning a physical finger from one account to another is always
delete-then-enroll — the duplicates check will refuse the enrollment while the
old template is still on the chip.

## Verifying

```bash
fprintd-list tapiiri          # show enrolled fingers
fprintd-list ilmari-offeri
fprintd-verify                # test a match without logging out
```

Both `tapiiri` and `ilmari-offeri` enroll separately. The sensor is shared
hardware and the templates share its storage, but fprintd tracks which slot
belongs to which user.

## Caveats

**The GNOME login keyring stays locked.** `pam_gnome_keyring` unlocks the login
keyring using your password. A fingerprint login has no password to hand over,
so the keyring is still locked when the session starts and the first consumer
(Chrome, Evolution, some `libsecret` users) pops an "unlock keyring" dialog.
Fingerprint unlock of an already-running session does not have this problem —
only the initial GDM login does. If it becomes annoying, the options are to
enter the password at GDM instead, or to set an empty keyring password
(which stores the keyring unencrypted — not recommended).

**1Password is unaffected.** Its system-authentication integration goes through
polkit, which accepts a fingerprint here.

**Reinstalls do not wipe the chip.** Templates survive in sensor flash, but
fprintd's record of which slot belongs to which user does not. Expect to
`sudo fprintd-delete <user>` and re-enroll after a fresh install — otherwise the
stale on-chip templates just occupy slots and reject re-enrollment as duplicates.

**Recovery.** The password path is never removed — `pam_fprintd` is `sufficient`
in `sudo`/polkit and runs *in parallel* with the password stack at GDM. A failed
or unreadable sensor degrades to a normal password prompt.
