// encodes and decodes any value into valid JSON
const codec = (() => {
    const typedArrays = {
        Int8Array, Uint8Array, Uint8ClampedArray,
        Int16Array, Uint16Array,
        Int32Array, Uint32Array,
        Float32Array, Float64Array,
        BigInt64Array, BigUint64Array,
        ...(typeof Float16Array === "undefined" ? {} : { Float16Array }),
    };

    const bytesToBase64 = bytes => {
        let text = "";
        for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        return btoa(text);
    };

    const base64ToBytes = base64 => Uint8Array.from(atob(base64), char => char.charCodeAt(0));

    async function encode(value, seen = new Map()) {
        // Encodes javascript types into valid JSON
        
        // 1. Primitives
        if (value === undefined) return { t: "undefined" };
        if (value === null || typeof value === "boolean" || typeof value === "string") return value;
        if (typeof value === "number") {
            if (Number.isNaN(value)) return { t: "NaN" };
            if (value === Infinity) return { t: "Infinity" };
            if (value === -Infinity) return { t: "-Infinity" };
            if (Object.is(value, -0)) return { t: "-0" };
            return value;
        }
        if (typeof value === "bigint") return { t: "bigint", value: value.toString() };

        // 2. Unsupported Types
        if (typeof value === "symbol") throw new TypeError("Cannot serialize Symbol");
        if (typeof value === "function") throw new TypeError("Cannot serialize Function");
        if (value instanceof Promise) throw new TypeError("Promises cannot be serialized");
        if (value instanceof WeakMap || value instanceof WeakSet) throw new TypeError("WeakMap and WeakSet cannot be serialized");
        if (typeof SharedArrayBuffer !== "undefined" && value instanceof SharedArrayBuffer)
            throw new TypeError("SharedArrayBuffer cannot be stored in IndexedDB");

        // 3. Handle references for ALL objects
        const existingID = seen.get(value);
        if (existingID !== undefined) return { t: "ref", id: existingID };

        const id = seen.size + 1;
        seen.set(value, id);

        if (value instanceof Date) return { t: "date", id: id, value: value.toISOString() };
        //#NOTE: possibly handle temporal
        if (value instanceof URL) return { t: "url", id: id, value: value.href };
        if (value instanceof RegExp) return { t: "regexp", id: id, source: value.source, flags: value.flags };
        if (typeof AggregateError !== "undefined" && value instanceof AggregateError) {
            const errors = [];
            for (const error of value.errors) { errors.push(await encode(error, seen)); }

            return { t: "aggregateError", id, message: value.message, stack: value.stack ?? "", errors };
        }
        if (typeof SuppressedError !== "undefined" && value instanceof SuppressedError) {
            return {
                t: "suppressedError", id, message: value.message, stack: value.stack ?? "",
                error: await encode(value.error, seen),
                suppressed: await encode(value.suppressed, seen),
            };
        }
        // catches TypeError, RangeError, SyntaxError, etc.
        if (value instanceof Error) return { t: "error", id: id, name: value.name, message: value.message, stack: value.stack ?? "" };
        if (value instanceof ArrayBuffer) return { t: "arrayBuffer", id: id, value: bytesToBase64(new Uint8Array(value)) };

        if (value instanceof DataView) {
            return {
                t: "dataView",
                id,
                buffer: await encode(value.buffer, seen),
                byteOffset: value.byteOffset,
                byteLength: value.byteLength
            };
        }

        if (ArrayBuffer.isView(value) && !(value instanceof DataView)) {
            return {
                t: "typedArray",
                id,
                name: value.constructor.name,
                buffer: await encode(value.buffer, seen),
                byteOffset: value.byteOffset,
                length: value.length
            };
        }
        
        // File must come before Blob because File extends Blob
        if (typeof File !== "undefined" && value instanceof File) {
            return {
                t: "file",
                id,
                name: value.name,
                type: value.type,
                lastModified: value.lastModified,
                value: bytesToBase64(new Uint8Array(await value.arrayBuffer()))
            };
        }
        if (value instanceof Blob) {
            return {
                t: "blob",
                id,
                type: value.type,
                value: bytesToBase64(new Uint8Array(await value.arrayBuffer()))
            };
        }

        if (Array.isArray(value)) {
            const items = [];
            for (let index = 0; index < value.length; index++) {
                if (Object.hasOwn(value, index)) items.push([index, await encode(value[index], seen)]);
            }
            return { t: "array", id, length: value.length, items };
        }

        if (value instanceof Map) {
            const items = [];
            for (const [key, item] of value)
            items.push([
                await encode(key, seen),
                await encode(item, seen)
            ]);

            return { t: "map", id, value: items };
        }

        if (value instanceof Set) {
            const items = [];
            for (const item of value) items.push(await encode(item, seen));
            return { t: "set", id, value: items };
        }

        // 4. Fallback for any object
        const items = [];
        for (const key of Object.keys(value)) items.push([key, await encode(value[key], seen)]);

        return { t: "object", id, value: items };
    }

    function decode(value, refs = new Map()) {
        if (value === null || typeof value !== "object") return value;

        switch (value.t) {
            // 1. Primitives
            case "undefined": return undefined;
            case "NaN": return NaN;
            case "Infinity": return Infinity;
            case "-Infinity": return -Infinity;
            case "-0": return -0;
            case "bigint": return BigInt(value.value);

            // 2. References
            case "ref": {
                if (!refs.has(value.id)) throw new Error(`Unknown reference: ${value.id}`);
                return refs.get(value.id);
            }
            case "date": {
                const result = new Date(value.value);
                refs.set(value.id, result); return result;
            }
            case "url": {
                const result = new URL(value.value);
                refs.set(value.id, result); return result;
            }
            case "regexp": {
                const result = new RegExp(value.source, value.flags);
                refs.set(value.id, result); return result;
            }
            case "arrayBuffer": {
                const result = base64ToBytes(value.value).buffer;
                refs.set(value.id, result); return result;
            }
            case "dataView": {
                const result = new DataView(decode(value.buffer, refs), value.byteOffset,value.byteLength);
                refs.set(value.id, result); return result;
            }
            case "typedArray": {
                const Type = typedArrays[value.name];
                if (!Type) throw new Error(`Unsupported typed array: ${value.name}`);

                const result = new Type(decode(value.buffer, refs),value.byteOffset, value.length);
                refs.set(value.id, result); return result;
            }
            case "blob": {
                const result = new Blob([base64ToBytes(value.value)],{ type: value.type });
                refs.set(value.id, result); return result;
            }
            case "file": {
                const result = new File([base64ToBytes(value.value)],value.name,{ type: value.type, lastModified: value.lastModified });
                refs.set(value.id, result); return result;
            }
            case "error": {
                const types = {Error, EvalError, RangeError, ReferenceError, SyntaxError, TypeError, URIError};
                const Type = types[value.name] ?? Error;
                const result = new Type(value.message);
                refs.set(value.id, result); 
                result.name = value.name;
                result.stack = value.stack;
                return result;
            }
            case "aggregateError": {
                if (typeof AggregateError === "undefined") throw new Error("AggregateError is unavailable in this browser");

                const result = new AggregateError([], value.message);
                refs.set(value.id, result); 
                result.stack = value.stack;
                result.errors = value.errors.map(item => decode(item, refs));
                return result;
            }
            case "suppressedError": {
                if (typeof SuppressedError === "undefined") throw new Error("SuppressedError is unavailable in this browser");

                const result = new SuppressedError(undefined, undefined, value.message);
                refs.set(value.id, result); 
                result.stack = value.stack;
                result.error = decode(value.error, refs);
                result.suppressed = decode(value.suppressed, refs);
                return result;
            }
            case "array": {
                const result = new Array(value.length);
                refs.set(value.id, result); 
                for (const [index, item] of value.items) result[index] = decode(item, refs);

                return result;
            }
            case "map": {
                const result = new Map();
                refs.set(value.id, result); 
                for (const [key, item] of value.value) result.set(decode(key, refs), decode(item, refs));

                return result;
            }
            case "set": {
                const result = new Set();
                refs.set(value.id, result);
                for (const item of value.value) result.add(decode(item, refs));

                return result;
            }

            case "object": {
                const result = {};
                refs.set(value.id, result);

                for (const [key, item] of value.value) {
                    if (key !== "__proto__") result[key] = decode(item, refs);
                }
                return result;
            }

            default: throw new Error(`Unknown encoded value type: ${value.t}`);
        }
    }

    return { encode, decode };
})();
    
const wait = request => new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
});

async function getIndexedDB() {
    return await Promise.all(
        (await indexedDB.databases())
        .filter(({ name }) => name !== undefined)
        .map(async ({ name }) => {
            const db = await wait(indexedDB.open(name));
            try {
                const stores = Object.fromEntries(
                    await Promise.all([...db.objectStoreNames].map(async name => {
                        const store = db.transaction(name, "readonly").objectStore(name);

                        const [keys, values] = await Promise.all([
                            wait(store.getAllKeys()),
                            wait(store.getAll()),
                        ]);

                        return [name, {
                            keyPath: store.keyPath,
                            autoIncrement: store.autoIncrement,
                            indexes: [...store.indexNames].map(name => {
                                const index = store.index(name);
                                return { name: index.name, keyPath: index.keyPath, unique: index.unique, multiEntry: index.multiEntry };
                            }),
                            records: await Promise.all(keys.map(async (key, i) => ({
                                key: await codec.encode(key), value: await codec.encode(values[i]),
                            }))),
                        }];
                    }))
                );

                return { name: db.name, version: db.version, stores };
            } finally { db.close(); }
        })
    );
}

async function loadIndexedDB(myIndexedDB) {
    await Promise.all(
      (await indexedDB.databases())
        .filter(({ name }) => name !== undefined)
        .map(({ name }) => wait(indexedDB.deleteDatabase(name))),
    );

    await Promise.all(myIndexedDB.map(async database => {
        const open = indexedDB.open(database.name, database.version);

        open.onupgradeneeded = () => {
            const db = open.result;

            for (const [name, store] of Object.entries(database.stores)) {
                const objectStore = db.createObjectStore(name, { keyPath: store.keyPath, autoIncrement: store.autoIncrement });

                for (const index of store.indexes) {
                    objectStore.createIndex(index.name, index.keyPath, { unique: index.unique, multiEntry: index.multiEntry });
                }
            }
        };

        const db = await wait(open);

        try {
            await Promise.all(Object.entries(database.stores).map(async ([name, store]) => {
                const tx = db.transaction(name, "readwrite");
                const objectStore = tx.objectStore(name);

                const done = new Promise((resolve, reject) => {
                    tx.oncomplete = resolve;
                    tx.onabort = () => reject(tx.error);
                });
                done.catch(() => {});

                try {
                    for (const record of store.records) {
                        const value = codec.decode(record.value);

                        if (store.keyPath === null) {
                            objectStore.add(value, codec.decode(record.key));
                        } else {
                            objectStore.add(value);
                        }
                    }
                } catch(error) { 
                    tx.abort(); throw error; 
                }
                await done;
            }));
        } finally { db.close(); }
    }));
    return true
}
