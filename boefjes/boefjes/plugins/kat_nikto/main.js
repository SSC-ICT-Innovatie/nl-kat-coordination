import fs from "node:fs";
import { execSync } from "node:child_process";

/**
 * @param {"http" | "https"} scheme
 * @returns {string}
 */
function get_config_content(scheme) {
  const IS_USING_PROXY = !!process.env.HTTP_PROXY;

  // Setup config file
  try {
    let config_contents =
      "PROMPTS=no\nUPDATES=no\nCLIOPTS=-404code=301,302,307,308 -o ./output.json";

    if (scheme == "https") config_contents += " -ssl";
    if (IS_USING_PROXY) config_contents += " -useproxy";
    config_contents += "\n";

    if (IS_USING_PROXY) {
      const PROXY = new URL(process.env.HTTP_PROXY);
      const PROXY_HOST = PROXY.hostname;
      const PROXY_PORT = PROXY.port || "8080";
      const PROXY_USER = PROXY.username || "";
      const PROXY_PASS = PROXY.password || "";

      config_contents += `PROXYHOST=${PROXY_HOST}\n`;
      config_contents += `PROXYPORT=${PROXY_PORT}\n`;
      config_contents += `PROXYUSER=${PROXY_USER}\n`;
      config_contents += `PROXYPASS=${PROXY_PASS}\n`;
    }

    if (process.env.USERAGENT)
      config_contents += `USERAGENT=${process.env.USERAGENT}\n`;

    return config_contents;
  } catch (e) {
    throw new Error("Something went wrong writing to the config file.\n" + e);
  }
}

/**
 * @param {Object} boefje_meta
 * @param {Object} boefje_meta.arguments
 * @param {Object} boefje_meta.arguments.input
 * @param {string} boefje_meta.arguments.input.object_type
 * @param {Object} boefje_meta.arguments.input.ip_service
 * @param {Object} boefje_meta.arguments.input.ip_service.ip_port
 * @param {Object} boefje_meta.arguments.input.ip_service.ip_port.address
 * @param {string} boefje_meta.arguments.input.ip_service.ip_port.address.address
 * @param {string} boefje_meta.arguments.input.ip_service.ip_port.port
 * @param {Object} boefje_meta.arguments.input.ip_service.service
 * @param {"http" | "https"} boefje_meta.arguments.input.ip_service.service.name
 * @param {Object} boefje_meta.arguments.input.hostname
 * @param {string} boefje_meta.arguments.input.hostname.name
 * @returns {(string | string[])[][]}
 */
export default function (boefje_meta) {
  // Depending on what OOI triggered this task, the hostname / address will be in a different location
  const hostname = boefje_meta.arguments.input.hostname.name;

  const config_contents = get_config_content(
    boefje_meta.arguments.input.ip_service.service.name,
  );
  fs.writeFileSync("./nikto.conf", config_contents);

  // Running nikto and outputting to a file
  try {
    execSync(`./nikto/program/nikto.pl -h ${hostname} -config ./nikto.conf`, {
      stdio: "inherit",
    });
  } catch (e) {
    throw new Error(
      "Something went wrong running the nikto command.\n" +
        e +
        "\n" +
        config_contents,
    );
  }

  const raws = [];

  // Reading the file created by nikto
  try {
    var file_contents = fs.readFileSync("./output.json").toString();

    raws.push([["boefje/nikto-output", "openkat/nikto-output"], file_contents]);
  } catch (e) {
    throw new Error(
      "Something went wrong reading the file from the nikto command.\n" + e,
    );
  }

  // Looking if outdated software has been found
  try {
    const data = JSON.parse(file_contents);
    if (data["vulnerabilities"])
      for (const vulnerability of data["vulnerabilities"])
        if (vulnerability["id"].startsWith("6"))
          raws.push([["openkat/finding"], "KAT-OUTDATED-SOFTWARE"]);
  } catch (e) {
    console.error(e);
  }

  return raws;
}
