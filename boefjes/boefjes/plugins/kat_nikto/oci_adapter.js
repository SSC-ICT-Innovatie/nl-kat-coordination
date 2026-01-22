import { execSync } from "node:child_process";
import run from "./main.js";

/**
 * @param {string} inp The string input to base64
 * @returns {string}
 */
function b64encode(inp) {
  return Buffer.from(inp).toString("base64");
}

function main() {
  const input_url = process.argv[process.argv.length - 1];

  // Getting the boefje input
  try {
    var boefje_input = JSON.parse(
      execSync(`curl --request GET --url ${input_url}`).toString(),
    );
  } catch (error) {
    console.error(`Getting boefje input went wrong with URL: ${input_url}`);
    throw new Error(error);
  }

  Object.assign(process.env, boefje_input["task"]["data"]["environment"]);

  let out = undefined;
  let output_url = boefje_input.output_url;
  try {
    // Getting the raw files
    const raws = run(boefje_input.task.data);
    out = {
      status: "COMPLETED",
      files: raws.map((x, i) => ({
        name: String(i),
        content: b64encode(x[1]),
        tags: x[0],
      })),
    };
  } catch (error) {
    out = {
      status: "FAILED",
      files: [
        {
          name: "error",
          content: b64encode("Boefje caught an error: " + error.message),
          tags: ["error/boefje"],
        },
      ],
    };
  }

  // Example command
  /*
    curl --request POST \
      --url http://boefje:8000/api/v0/tasks/7342e8dd-b945-4185-aaec-787205b7b664 \
      --header 'Content-Type: application/json' \
      --data '{"status":"COMPLETED","files":[{"content":"BASE_64_ENCODED_CONTENT","tags":[]}]}'
  */
  const out_json = JSON.stringify(out);
  const cmd = `curl --request POST --url ${output_url} --header "Content-Type: application/json" --data '${out_json}'`;

  execSync(cmd);
}

main();
