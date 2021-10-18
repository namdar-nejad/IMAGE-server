import express from "express";
import sharp from "sharp";
import Ajv from "ajv";

import querySchemaJSON from "./schemas/request.schema.json";
import handlerResponseSchemaJSON from "./schemas/handler-response.schema.json";
import definitionsJSON from "./schemas/definitions.json";

const app = express();
const port = 80;
const ajv = new Ajv({
    "schemas": [querySchemaJSON, definitionsJSON, handlerResponseSchemaJSON]
});

async function extractDimensions(dataUrl: string) {
    const imageBuffer = Buffer.from(dataUrl.split(",")[1], "base64");
    const metadata = await sharp(imageBuffer).metadata();
    return [metadata.width as number, metadata.height as number];
}

function generateRendering(width: number, height: number): object {
    return {
        "type_id": "ca.mcgill.a11y.image.renderer.Text",
        "confidence": 100,
        "description": "An example rendering that conveys no useful information.",
        "metadata": {
            "description": "This was generated by the \"hello handler\" container, an example of how to structure a handler. It is not meant to be used in production."
        },
        "data": {
            "text": `The image received is ${width} pixels by ${height} pixels.`
        }
    };
}

app.use(express.json({ limit: process.env.MAX_BODY }));

app.post("/handler", async (req, res) => {
    if (ajv.validate("https://image.a11y.mcgill.ca/request.schema.json", req.body)) {
        // tslint:disable-next-line:no-console
        console.log("Request validated");
        if (!req.body.image) {
            console.log("Not an image request! Skipping...");
            res.status(204);
            return;
        }
        // Check for text rendering support
        const renderers = req.body.renderers as string[];
        let rendering = [];
        if (renderers.includes("ca.mcgill.a11y.image.renderer.Text")) {
            const dims = await extractDimensions(req.body.image);
            rendering.push(generateRendering(dims[0], dims[1]));
        } else {
            // tslint:disable-next-line:no-console
            console.warn("Text renderer not supported by the client!");
        }
        const response = {
            "request_uuid": req.body.request_uuid,
            "timestamp": Math.round(Date.now() / 1000),
            "renderings": rendering
        };
        if (ajv.validate("https://image.a11y.mcgill.ca/handler-response.schema.json", response)) {
            // tslint:disable-next-line:no-console
            console.log("Valid response generated.");
            res.json(response);
        } else {
            // tslint:disable-next-line:no-console
            console.log("Failed to generate a valid response (did the schema change?)");
            res.status(500).json(ajv.errors);
        }
    } else {
        // tslint:disable-next-line:no-console
        console.log("Request did not pass the schema.");
        res.status(400).send(ajv.errors);
    }
});

app.listen(port, () => {
    // tslint:disable-next-line:no-console
    console.log(`Started server on port ${port}`);
});
