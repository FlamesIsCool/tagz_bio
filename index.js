const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');
const querystring = require('querystring');

const DATA_FILE = path.join(__dirname, 'data', 'users.json');

function loadUsers() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE));
  } catch (e) {
    return {};
  }
}

function saveUsers(users) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(users, null, 2));
}

const users = loadUsers();

function renderTemplate(title, content) {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { background: #000; color: #cfc; font-family: Arial, sans-serif; margin: 0; padding: 20px; }
    a { color: #5f5; }
    .container { max-width: 600px; margin: auto; }
    input[type=text], input[type=submit] { padding: 10px; margin-top: 10px; width: 100%; }
    input[type=submit] { background: #0a0; color: #fff; border: none; cursor: pointer; }
  </style>
</head>
<body>
<div class="container">
${content}
</div>
</body>
</html>`;
}

function homePage() {
  return renderTemplate('tagz.lol', `
    <h1>tagz.lol</h1>
    <form method="POST" action="/claim">
      <label for="username">Claim your username:</label><br>
      <input type="text" id="username" name="username" required pattern="[A-Za-z0-9_]{3,15}"><br>
      <input type="submit" value="Claim">
    </form>
  `);
}

function claimUsername(req, res, body) {
  const { username } = querystring.parse(body);
  const clean = (username || '').toLowerCase();
  if (!clean || !/^[a-z0-9_]{3,15}$/.test(clean)) {
    res.writeHead(400, { 'Content-Type': 'text/html' });
    res.end(renderTemplate('Error', '<p>Invalid username.</p><a href="/">Back</a>'));
    return;
  }
  if (users[clean]) {
    res.writeHead(409, { 'Content-Type': 'text/html' });
    res.end(renderTemplate('Taken', '<p>Username already taken.</p><a href="/">Back</a>'));
    return;
  }
  users[clean] = {
    username: clean,
    description: '',
    accentColor: '#00aa00',
    textColor: '#ffffff',
    backgroundColor: '#000000'
  };
  saveUsers(users);
  res.writeHead(302, { Location: `/customize?user=${clean}` });
  res.end();
}

function customizePage(name) {
  const user = users[name];
  if (!user) return null;
  return renderTemplate('Customize', `
    <h1>Customize @${name}</h1>
    <form method="POST" action="/customize?user=${name}">
      <label for="description">Description</label><br>
      <input type="text" id="description" name="description" value="${user.description || ''}"><br>

      <label for="accentColor">Accent Color</label><br>
      <input type="text" id="accentColor" name="accentColor" value="${user.accentColor}"><br>

      <label for="textColor">Text Color</label><br>
      <input type="text" id="textColor" name="textColor" value="${user.textColor}"><br>

      <label for="backgroundColor">Background Color</label><br>
      <input type="text" id="backgroundColor" name="backgroundColor" value="${user.backgroundColor}"><br>
      <input type="submit" value="Save">
    </form>
  `);
}

function saveCustomization(req, res, name, body) {
  const user = users[name];
  if (!user) {
    res.writeHead(404, { 'Content-Type': 'text/html' });
    res.end(renderTemplate('Not Found', '<p>User not found.</p>'));
    return;
  }
  const data = querystring.parse(body);
  user.description = data.description || '';
  user.accentColor = data.accentColor || user.accentColor;
  user.textColor = data.textColor || user.textColor;
  user.backgroundColor = data.backgroundColor || user.backgroundColor;
  saveUsers(users);
  res.writeHead(302, { Location: `/${name}` });
  res.end();
}

function userPage(name) {
  const user = users[name];
  if (!user) return null;
  return renderTemplate(`@${name}`, `
    <div style="background:${user.backgroundColor};color:${user.textColor};padding:20px;border:2px solid ${user.accentColor};">
      <h1 style="color:${user.accentColor}">@${name}</h1>
      <p>${user.description}</p>
      <p><a href="/customize?user=${name}">Edit profile</a></p>
    </div>
  `);
}

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url);
  if (req.method === 'GET' && parsed.pathname === '/') {
    res.writeHead(200, {'Content-Type': 'text/html'});
    res.end(homePage());
  } else if (req.method === 'POST' && parsed.pathname === '/claim') {
    let body = '';
    req.on('data', chunk => body += chunk.toString());
    req.on('end', () => claimUsername(req, res, body));
  } else if (req.method === 'GET' && parsed.pathname === '/customize') {
    const name = (querystring.parse(parsed.query).user || '').toLowerCase();
    const page = customizePage(name);
    if (page) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(page);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/html' });
      res.end(renderTemplate('Not Found', '<p>User not found.</p>'));
    }
  } else if (req.method === 'POST' && parsed.pathname === '/customize') {
    const name = (querystring.parse(parsed.query).user || '').toLowerCase();
    let body = '';
    req.on('data', chunk => body += chunk.toString());
    req.on('end', () => saveCustomization(req, res, name, body));
  } else if (req.method === 'GET') {
    const name = parsed.pathname.slice(1).toLowerCase();
    const page = userPage(name);
    if (page) {
      res.writeHead(200, {'Content-Type': 'text/html'});
      res.end(page);
    } else {
      res.writeHead(404, {'Content-Type': 'text/html'});
      res.end(renderTemplate('Not Found', '<p>User not found.</p>'));
    }
  } else {
    res.writeHead(404);
    res.end();
  }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
