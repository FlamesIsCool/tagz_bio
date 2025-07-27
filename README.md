# tagz.lol

Simple social bio link service where users claim unique usernames.

## Usage

1. Ensure Node.js is installed.
2. Run `npm start` to launch the server (defaults to port 3000).
3. Open `http://localhost:3000` in your browser.

Usernames must be 3-15 characters of letters, numbers, or underscore and are stored in `data/users.json`.

After claiming a username you will be taken to a customize page where you can add a short description and choose colors for your profile. Submitting the form will save the settings and redirect you to your public profile page.
