import { timingSafeEqual } from "node:crypto";
import { eveChannel } from "eve/channels/eve";

export default eveChannel({
  auth(request) {
    const secreto = process.env.CONFORME_EVE_TOKEN;
    const recibido = request.headers.get("authorization");
    if (!secreto || !recibido) return null;
    const esperado = Buffer.from(`Bearer ${secreto}`);
    const credencial = Buffer.from(recibido);
    if (credencial.length !== esperado.length || !timingSafeEqual(credencial, esperado)) return null;
    return { authenticator: "conforme", principalId: "conforme-api", principalType: "service" };
  },
});
