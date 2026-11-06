// Worker de Cloudflare que sirve de puente para la API de Cinépolis
// (api-g.cinepolis.com), que bloquea con 403 a los runners de GitHub
// Actions por reputación de IP (la huella TLS de Chrome no basta).
//
// Cómo desplegarlo (dashboard, unos 5 minutos):
//   1. dash.cloudflare.com → Workers & Pages → Create Worker → Deploy
//      (con el código de ejemplo que trae, no importa).
//   2. Edita el código y pega este fichero entero → Deploy.
//   3. Worker → Settings → Variables and Secrets, añade:
//        PROXY_TOKEN      = (el mismo valor que luego va al secreto
//                          YELMO_PROXY_TOKEN de GitHub)
//        CINEPOLIS_APIKEY = lQM6Mkvri1iHksKKCfpAiwGXq0YUZA7Nn6XAXRPr4i13LwXo
//                          (la clave pública que envía la propia web;
//                          si Cinépolis la rota, se cambia aquí)
//   4. Copia la URL tipo https://yelmo-proxy.tu-subdomain.workers.dev
//      y créala en GitHub como secreto YELMO_WORKER_URL.
//   5. Crea también el secreto YELMO_PROXY_TOKEN con el mismo valor
//      del paso 3.
//
// El token evita que cualquiera que encuentre la URL gaste las cuotas
// de la API en nuestro nombre.

const API_URL = "https://api-g.cinepolis.com/v2/billboards/graphql";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("usar POST", { status: 405 });
    }
    if (request.headers.get("x-proxy-token") !== env.PROXY_TOKEN) {
      return new Response("token invalido", { status: 401 });
    }

    // Los encabezados que la web envía desde el navegador: la x-apikey
    // pública identifica al cliente web, no a un usuario.
    const respuesta = await fetch(API_URL, {
      method: "POST",
      headers: {
        accept: "*/*",
        "content-type": "application/json",
        "country-id": request.headers.get("country-id") || "ES",
        language: request.headers.get("language") || "es",
        "x-apikey": env.CINEPOLIS_APIKEY,
        origin: "https://cineyelmo.com",
        referer: "https://cineyelmo.com/",
      },
      body: await request.text(),
    });

    return new Response(await respuesta.text(), {
      status: respuesta.status,
      headers: {
        "content-type": respuesta.headers.get("content-type") || "application/json",
      },
    });
  },
};
