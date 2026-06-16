#!/bin/bash
# À lancer depuis le terminal Render (Shell tab) pour diagnostiquer

echo "=== Test route /api/test-email ==="
curl -s -X POST http://localhost:$PORT/api/test-email \
  -H "Content-Type: application/json" \
  -d '{"senderEmail":"test@gmail.com","appPassword":"aaaa bbbb cccc dddd"}' \
  -w "\nHTTP status: %{http_code}\n"

echo ""
echo "=== Headers de la réponse ==="
curl -s -I -X POST http://localhost:$PORT/api/test-email \
  -H "Content-Type: application/json" \
  -d '{"senderEmail":"test@gmail.com","appPassword":"aaaaaaaaaaaaaaaa"}'
