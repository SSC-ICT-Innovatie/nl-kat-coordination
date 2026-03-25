import run from "./main.js";

/**
 * @param {string} inp The string input to base64
 * @returns {string}
 */
function b64encode(inp) {
  return Buffer.from(inp).toString("base64");
}

async function main() {
  const input_url = process.argv[process.argv.length - 1];

  // Getting the boefje input
  let boefje_input;
  try {
    const input_response = await fetch(input_url);
    boefje_input = await input_response.json();
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

  const out_json = JSON.stringify(out);
  await fetch(output_url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: out_json,
  });
}

main();
