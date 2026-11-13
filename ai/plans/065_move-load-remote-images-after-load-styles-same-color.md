# Move "Load remote images" after "Load styles", same color

## Context

Todo `2a7dff4f-1ee0-429a-a32c-a0b9e8bfb82f`: "move the load images button after the load styles button", note "same color as styles".
Today `MailMessage.vue` (`frontend/src/components/MailMessage.vue`, lines ~172-203) shows the two load buttons in different places and styles.
`Load remote images` sits at the bottom of the collapsed `Blocked images (n)` disclosure with the default accent button style.
`Load styles` is a `ghost` button in the `styles-blocked` hint line, below the disclosure.

## Findings

- `.ghost` (`styles/main.scss:111`) is the outline style the styles button uses, so "same color" means giving the images button the `ghost` class.
- `.blocked-images` (`main.scss:1524`) is only the bordered disclosure box, there is no style tied to `.load-remote`.
- The only test touching the button is `frontend/e2e/mail.spec.ts:364` (`lists the blocked images and loads them on request`): it opens the disclosure, clicks the button by name `Load remote images`, then expects `.blocked-images` to be gone.
- Both buttons call `store.allow(...)` and are disabled offline with the same title, so the behaviour stays untouched.

## Change

1. In `MailMessage.vue`, take the `Load remote images` button out of the `<details class="blocked-images">`, so the disclosure only lists the URLs.
2. Put it right after the `Load styles` button, with `class="ghost load-remote"`, the same `:disabled` / `:title` handling and `@click="store.allow({ remoteImages: true })"`.
3. The two buttons share one row `<p class="hint load-actions">` shown when `showHtml` and (`styles_blocked` or `blocked_images.length`).
   - The text "The styles of this mail are not shown." only renders when `styles_blocked`.
   - `Load styles` only renders when `styles_blocked`, `Load remote images` only when there are blocked images, always in that order.
   - Keep the `styles-blocked` class on the text span so nothing else needs to change; the row sits below the disclosure as today.
4. A small gap between the buttons, via the existing `.hint` row (add `display: flex; flex-wrap: wrap; gap: 8px; align-items: center` to `.load-actions` in `main.scss` next to `.blocked-images`).
5. Update the e2e test: after opening the disclosure and checking the links, click `Load remote images` (it is now visible without opening the disclosure, so the click works either way), keep the rest.
   Add an assertion that in the DOM the `Load remote images` button follows `Load styles` and has the `ghost` class when both are blocked, if the mock mail for the test has blocked styles (check `openThird`'s fixture, otherwise assert only the ghost class).
6. `CLAUDE.md`: no behavior of note changes, only add half a sentence to the "Mail view" bullet that both load buttons share one row, in this order.

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build`, and `yarn test:e2e e2e/mail.spec.ts` (Chromium and `webkit-ipad`).
- Playwright screenshot of a mail with blocked images and styles to confirm the order and the color.
- Backend untouched, so `uv run pytest` is only a sanity run.
