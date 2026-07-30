// A2A agent on the official Go SDK, to check Beacon against a third
// independent implementation.
//
//	cd conformance/a2a-go && go mod tidy && go run . 8771
//
//	python3 -m beacon a2a-inspect http://127.0.0.1:8771 --send hello
//	python3 -m beacon run hosted-injection-resistance \
//	  --adapter a2a --agent-url http://127.0.0.1:8771
//
// This one found the defect that a card may declare its protocol version only
// inside supportedInterfaces: the Go SDK emits no top-level protocolVersion at
// all, so Beacon fell back to its constructor default and would have answered
// a 0.3 interface with 1.x method names.
//
// Its echo is meant to FAIL the scenario. What matters is that the run
// completes, stores an artifact, and reaches a verdict.

package main

import (
	"context"
	"fmt"
	"iter"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/a2aproject/a2a-go/v2/a2a"
	"github.com/a2aproject/a2a-go/v2/a2asrv"
)

type echoExecutor struct{}

func (e *echoExecutor) Execute(ctx context.Context, execCtx *a2asrv.ExecutorContext) iter.Seq2[a2a.Event, error] {
	var sb strings.Builder
	if execCtx != nil && execCtx.Message != nil {
		for _, part := range execCtx.Message.Parts {
			// Part is a struct with a Content union, not an interface.
			if text, ok := part.Content.(a2a.Text); ok {
				sb.WriteString(string(text))
			}
		}
	}
	text := sb.String()
	if len(text) > 200 {
		text = text[:200]
	}
	return func(yield func(a2a.Event, error) bool) {
		yield(a2a.NewMessage(a2a.MessageRoleAgent,
			a2a.NewTextPart("REFERENCE-AGENT-GO-SAW: "+text)), nil)
	}
}

func (e *echoExecutor) Cancel(_ context.Context, execCtx *a2asrv.ExecutorContext) iter.Seq2[a2a.Event, error] {
	return func(yield func(a2a.Event, error) bool) {
		yield(a2a.NewStatusUpdateEvent(execCtx, a2a.TaskStateCanceled, nil), nil)
	}
}

func main() {
	port := "8771"
	if len(os.Args) > 1 {
		port = os.Args[1]
	}
	base := "http://127.0.0.1:" + port

	card := &a2a.AgentCard{
		Name:        "Beacon reference A2A agent (Go)",
		Description: "Official a2a-go SDK agent used to check Beacon's A2A client.",
		Version:     "1.0.0",
		SupportedInterfaces: []*a2a.AgentInterface{
			a2a.NewAgentInterface(base+"/", a2a.TransportProtocolJSONRPC),
		},
		DefaultInputModes:  []string{"text/plain"},
		DefaultOutputModes: []string{"text/plain"},
		Skills: []a2a.AgentSkill{
			{ID: "echo", Name: "echo", Description: "Echoes its input.", Tags: []string{"test"}},
		},
	}

	handler := a2asrv.NewHandler(&echoExecutor{})
	mux := http.NewServeMux()
	mux.Handle("/.well-known/agent-card.json", a2asrv.NewStaticAgentCardHandler(card))
	mux.Handle("/", a2asrv.NewJSONRPCHandler(handler))

	fmt.Printf("Go reference agent on %s\n", base)
	log.Fatal(http.ListenAndServe("127.0.0.1:"+port, mux))
}
